from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pytest_mock import MockerFixture
from starlette.types import Scope

from app.dicom.constants import DICOM_JSON_MEDIA_TYPES, MULTIPART_DICOM_MEDIA_TYPES
from app.dicom.exceptions import (
    DicomFrameNotFoundError,
    DicomNotFoundError,
    DicomRenderingError,
    DicomRepresentationNotSupportedError,
)
from app.dicom.repositories import DicomRepository
from app.dicom.schemas import DicomInstance, MultipartDicomPayload
from app.dicom.services import (
    DicomAcceptHeaderValidator,
    DicomJpegRenderer,
    DicomMetadataBuilder,
    DicomRouteHandler,
)
from app.hcim.constants import MEDMIJ_REQUEST_ID_HEADER


def build_request(path: str, headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode(), value.encode())
        for name, value in (headers or {}).items()
    ]
    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": encoded_headers,
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "root_path": "",
    }
    return Request(scope)


@pytest.fixture
def dicom_instance(tmp_path: Path) -> DicomInstance:
    dicom_path = tmp_path / "instance.dcm"
    dicom_path.touch()
    return DicomInstance(
        document_id="doc-1",
        path=dicom_path,
        study_uid="1.2.3",
        series_uid="1.2.3.1",
        instance_uid="1.2.3.1.1",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
        number_of_frames=1,
        modality="CT",
        study_description="Study",
        series_description="Series",
        body_part_examined="CHEST",
    )


@pytest.fixture
def mocked_request() -> Request:
    return build_request("/9000002/dicom/doc-1.dcm")


class TestDicomAcceptHeaderValidator:
    @pytest.mark.parametrize(
        ("accept_header", "media_type"),
        [
            ("application/dicom", "application/dicom"),
            ("*/*", "application/dicom"),
            ("application/*", "application/dicom"),
            ("application/dicom;q=0.8", "application/dicom"),
            ("text/html, application/dicom", "application/dicom"),
        ],
    )
    def test_header_accepts_media_type(
        self, accept_header: str, media_type: str
    ) -> None:
        assert (
            DicomAcceptHeaderValidator().header_accepts_media_type(
                accept_header, media_type
            )
            is True
        )

    @pytest.mark.parametrize(
        ("accept_header", "media_type"),
        [(None, "application/dicom"), ("text/html", "application/dicom")],
    )
    def test_header_rejects_media_type(
        self, accept_header: str | None, media_type: str
    ) -> None:
        assert (
            DicomAcceptHeaderValidator().header_accepts_media_type(
                accept_header, media_type
            )
            is False
        )

    def test_validate_supported_media_types_accepts_matching_header(self) -> None:
        DicomAcceptHeaderValidator().validate_supported_media_types(
            "application/dicom",
            {"application/dicom"},
        )

    def test_validate_supported_media_types_allows_missing_header(self) -> None:
        DicomAcceptHeaderValidator().validate_supported_media_types(
            None, {"application/dicom"}
        )

    def test_validate_supported_media_types_raises_for_unsupported_header(self) -> None:
        with pytest.raises(DicomRepresentationNotSupportedError):
            DicomAcceptHeaderValidator().validate_supported_media_types(
                "application/pdf",
                {"application/dicom"},
            )

    def test_validate_supported_media_types_accepts_multipart_for_study_series_retrieve(
        self,
    ) -> None:
        DicomAcceptHeaderValidator().validate_supported_media_types(
            'multipart/related; type="application/dicom"',
            MULTIPART_DICOM_MEDIA_TYPES,
        )

    def test_validate_supported_media_types_rejects_application_dicom_for_study_series_retrieve(
        self,
    ) -> None:
        with pytest.raises(DicomRepresentationNotSupportedError):
            DicomAcceptHeaderValidator().validate_supported_media_types(
                "application/dicom",
                MULTIPART_DICOM_MEDIA_TYPES,
            )

    def test_validate_supported_media_types_rejects_plain_json_for_metadata_endpoints(
        self,
    ) -> None:
        with pytest.raises(DicomRepresentationNotSupportedError):
            DicomAcceptHeaderValidator().validate_supported_media_types(
                "application/json",
                DICOM_JSON_MEDIA_TYPES,
            )


class TestDicomMetadataBuilder:
    def test_build_series_manifest_returns_one_entry_per_series(
        self, dicom_instance: DicomInstance
    ) -> None:
        builder = DicomMetadataBuilder()

        result = builder.build_series_manifest(
            study_uid=dicom_instance.study_uid,
            study_instances=(dicom_instance,),
            series_url_resolver=lambda series_uid: f"/series/{series_uid}",
        )

        assert result == [
            {
                "0020000D": {"vr": "UI", "Value": ["1.2.3"]},
                "0020000E": {"vr": "UI", "Value": ["1.2.3.1"]},
                "00080060": {"vr": "CS", "Value": ["CT"]},
                "00081030": {"vr": "LO", "Value": ["Study"]},
                "0008103E": {"vr": "LO", "Value": ["Series"]},
                "00081190": {"vr": "UR", "Value": ["/series/1.2.3.1"]},
            }
        ]

    def test_build_instance_metadata_adds_optional_fields_only_when_available(
        self,
        dicom_instance: DicomInstance,
    ) -> None:
        builder = DicomMetadataBuilder()
        with_frames = dicom_instance.__class__(
            **{**dicom_instance.__dict__, "number_of_frames": 3}
        )
        without_body_part = dicom_instance.__class__(
            **{
                **dicom_instance.__dict__,
                "body_part_examined": None,
                "number_of_frames": 1,
            }
        )

        frames_entry, without_body_part_entry = builder.build_instance_metadata(
            (with_frames, without_body_part)
        )

        assert frames_entry["00180015"]["Value"] == ["CHEST"]
        assert frames_entry["00280008"]["Value"] == ["3"]
        assert "00081160" not in frames_entry
        assert "00180015" not in without_body_part_entry
        assert "00280008" not in without_body_part_entry


class TestDicomJpegRenderer:
    def test_render_instance_as_jpeg_rejects_negative_frame_id(
        self,
        mocker: MockerFixture,
        dicom_instance: DicomInstance,
    ) -> None:
        repository = mocker.Mock()
        repository.read_dataset.return_value = mocker.Mock(
            pixel_array=np.zeros((2, 2), dtype=np.uint8)
        )

        with pytest.raises(DicomFrameNotFoundError, match="Frame ids start at 1"):
            DicomJpegRenderer(repository).render_instance_as_jpeg(dicom_instance, -1)

    def test_render_instance_as_jpeg_rejects_frame_beyond_range(
        self,
        mocker: MockerFixture,
        dicom_instance: DicomInstance,
    ) -> None:
        repository = mocker.Mock()
        repository.read_dataset.return_value = mocker.Mock(
            pixel_array=np.zeros((2, 2), dtype=np.uint8)
        )

        with pytest.raises(DicomFrameNotFoundError, match="not available"):
            DicomJpegRenderer(repository).render_instance_as_jpeg(dicom_instance, 2)

    def test_render_instance_as_jpeg_rejects_frame_zero_for_single_frame_instance(
        self,
        mocker: MockerFixture,
        dicom_instance: DicomInstance,
    ) -> None:
        repository = mocker.Mock()
        dataset = mocker.Mock()
        dataset.pixel_array = np.array([[100, 150], [200, 250]], dtype=np.uint8)
        dataset.PhotometricInterpretation = "MONOCHROME2"
        repository.read_dataset.return_value = dataset

        with pytest.raises(DicomFrameNotFoundError, match="not available"):
            DicomJpegRenderer(repository).render_instance_as_jpeg(dicom_instance, 0)

    def test_render_instance_as_jpeg_renders_requested_multiframe_image(
        self,
        mocker: MockerFixture,
        dicom_instance: DicomInstance,
    ) -> None:
        repository = mocker.Mock()
        dataset = mocker.Mock()
        dataset.pixel_array = np.array(
            [
                [[10, 20], [30, 40]],
                [[50, 60], [70, 80]],
                [[90, 100], [110, 120]],
            ],
            dtype=np.uint8,
        )
        dataset.PhotometricInterpretation = "MONOCHROME2"
        repository.read_dataset.return_value = dataset
        multiframe_instance = dicom_instance.__class__(
            **{
                **dicom_instance.__dict__,
                "number_of_frames": 3,
                "body_part_examined": None,
            }
        )

        result = DicomJpegRenderer(repository).render_instance_as_jpeg(
            multiframe_instance, 2
        )

        assert isinstance(result, bytes)
        assert result

    def test_render_instance_as_jpeg_renders_single_frame_for_default_and_explicit_frame_one(
        self,
        mocker: MockerFixture,
        dicom_instance: DicomInstance,
    ) -> None:
        repository = mocker.Mock()
        dataset = mocker.Mock()
        dataset.pixel_array = np.array([[100, 150], [200, 250]], dtype=np.uint8)
        dataset.PhotometricInterpretation = "MONOCHROME2"
        repository.read_dataset.return_value = dataset
        renderer = DicomJpegRenderer(repository)

        default_result = renderer.render_instance_as_jpeg(dicom_instance, None)
        explicit_result = renderer.render_instance_as_jpeg(dicom_instance, 1)

        assert isinstance(default_result, bytes)
        assert isinstance(explicit_result, bytes)
        assert default_result
        assert explicit_result

    def test_image_from_pixel_array_supports_monochrome_and_rgb(
        self,
        mocker: MockerFixture,
    ) -> None:
        renderer = DicomJpegRenderer(mocker.Mock())

        monochrome = renderer._image_from_pixel_array(
            np.array([[0, 100], [150, 255]], dtype=np.uint8),
            "MONOCHROME1",
        )
        rgb = renderer._image_from_pixel_array(
            np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8),
            "RGB",
        )

        assert monochrome.mode == "L"
        assert rgb.size == (2, 1)

    def test_image_from_pixel_array_rejects_unsupported_dimension(
        self,
        mocker: MockerFixture,
    ) -> None:
        with pytest.raises(DicomRenderingError):
            DicomJpegRenderer(mocker.Mock())._image_from_pixel_array(
                np.array([1, 2, 3]),
                "MONOCHROME2",
            )

    def test_normalize_to_uint8_returns_zeros_for_constant_array(
        self,
        mocker: MockerFixture,
    ) -> None:
        result = DicomJpegRenderer(mocker.Mock())._normalize_to_uint8(
            np.array([[5.0, 5.0], [5.0, 5.0]], dtype=np.float32)
        )

        assert result.dtype == np.uint8
        assert np.all(result == 0)


@pytest.fixture
def route_handler(
    mocker: MockerFixture,
) -> tuple[DicomRouteHandler, dict[str, Any]]:
    dependencies: dict[str, Any] = {
        "repository": mocker.Mock(spec=DicomRepository),
        "accept_validator": mocker.Mock(spec=DicomAcceptHeaderValidator),
        "metadata_builder": mocker.Mock(spec=DicomMetadataBuilder),
        "manifest_builder": mocker.Mock(),
        "jpeg_renderer": mocker.Mock(spec=DicomJpegRenderer),
    }
    handler = DicomRouteHandler(
        repository=dependencies["repository"],
        accept_validator=dependencies["accept_validator"],
        metadata_builder=dependencies["metadata_builder"],
        manifest_builder=dependencies["manifest_builder"],
        jpeg_renderer=dependencies["jpeg_renderer"],
    )
    return handler, dependencies


class TestDicomRouteHandler:
    @pytest.fixture(autouse=True)
    def _set_medmij_request_id(self, medmij_request_id: str) -> None:
        self.medmij_request_id = medmij_request_id

    def test_handle_dicom_returns_file_response_for_existing_instance(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies[
            "repository"
        ].get_instance_by_document_id.return_value = dicom_instance

        result = handler.handle_dicom(
            "doc-1", mocked_request, "application/dicom", self.medmij_request_id
        )

        assert isinstance(result, FileResponse)

    def test_handle_dicom_raises_when_file_is_missing_on_disk(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        missing_instance = dicom_instance.__class__(
            **{**dicom_instance.__dict__, "path": Path("/missing/file.dcm")}
        )
        dependencies[
            "repository"
        ].get_instance_by_document_id.return_value = missing_instance

        with pytest.raises(DicomNotFoundError, match="not available on disk"):
            handler.handle_dicom(
                "doc-1", mocked_request, "application/dicom", self.medmij_request_id
            )

    def test_handle_study_series_manifest_returns_dicom_json_only(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies["repository"].get_study_instances.return_value = (dicom_instance,)
        dependencies["accept_validator"].header_accepts_media_type.return_value = True
        dependencies["metadata_builder"].build_series_manifest.return_value = [
            {"series": "value"}
        ]

        result = handler.handle_study_series_manifest(
            "1.2.3",
            mocked_request,
            "application/dicom+json",
            self.medmij_request_id,
        )

        assert isinstance(result, JSONResponse)
        assert result.media_type == "application/dicom+json"
        dependencies["manifest_builder"].build_kos_document.assert_not_called()

    def test_handle_study_series_manifest_returns_dicom_json_when_requested(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies["repository"].get_study_instances.return_value = (dicom_instance,)
        dependencies["accept_validator"].header_accepts_media_type.return_value = False
        dependencies["metadata_builder"].build_series_manifest.return_value = [
            {"series": "value"}
        ]

        result = handler.handle_study_series_manifest(
            "1.2.3",
            mocked_request,
            "application/dicom+json",
            self.medmij_request_id,
        )

        assert isinstance(result, JSONResponse)
        assert result.media_type == "application/dicom+json"

    def test_handle_study_metadata_returns_dicom_json_entries(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies["repository"].get_study_instances.return_value = (dicom_instance,)
        dependencies["accept_validator"].header_accepts_media_type.return_value = False
        dependencies["metadata_builder"].build_instance_metadata.return_value = [
            {"instance": "value"}
        ]

        result = handler.handle_study_metadata(
            "1.2.3",
            mocked_request,
            "application/dicom+json",
            self.medmij_request_id,
        )

        assert isinstance(result, JSONResponse)

    def test_handle_study_metadata_never_builds_kos_document(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies["repository"].get_study_instances.return_value = (dicom_instance,)
        dependencies["accept_validator"].header_accepts_media_type.return_value = True
        dependencies["metadata_builder"].build_instance_metadata.return_value = [
            {"instance": "value"}
        ]

        handler.handle_study_metadata(
            "1.2.3", mocked_request, "application/dicom+json", self.medmij_request_id
        )

        dependencies["manifest_builder"].build_kos_document.assert_not_called()

    def test_handle_study_and_series_return_multipart_payloads(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        payload = MultipartDicomPayload(boundary="boundary", content=b"payload")
        dependencies["manifest_builder"].build_multipart_payload.return_value = payload
        dependencies["repository"].get_study_instances.return_value = (dicom_instance,)
        dependencies["repository"].get_series_instances.return_value = (dicom_instance,)

        study_result = handler.handle_study(
            "1.2.3",
            mocked_request,
            'multipart/related; type="application/dicom"',
            self.medmij_request_id,
        )
        series_result = handler.handle_series(
            "1.2.3",
            "1.2.3.1",
            mocked_request,
            'multipart/related; type="application/dicom"',
            self.medmij_request_id,
        )

        assert study_result.headers["Content-Type"].endswith('boundary="boundary"')
        assert series_result.headers["Content-Type"].endswith('boundary="boundary"')

    def test_handle_series_metadata_returns_json_entries(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        mocked_request: Request,
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        dependencies["repository"].get_series_instances.return_value = (dicom_instance,)
        dependencies["metadata_builder"].build_instance_metadata.return_value = [
            {"instance": "value"}
        ]

        result = handler.handle_series_metadata(
            "1.2.3",
            "1.2.3.1",
            mocked_request,
            "application/dicom+json",
            self.medmij_request_id,
        )

        assert isinstance(result, JSONResponse)

    def test_handle_instance_and_rendered_instance_delegate_to_dependencies(
        self,
        route_handler: tuple[DicomRouteHandler, dict[str, Any]],
        dicom_instance: DicomInstance,
    ) -> None:
        handler, dependencies = route_handler
        request = build_request(
            "/9000002/wado/studies/1.2.3/series/1.2.3.1/instances/1.2.3.1.1",
            {MEDMIJ_REQUEST_ID_HEADER: self.medmij_request_id},
        )
        dependencies["repository"].get_instance_by_uids.return_value = dicom_instance
        dependencies["jpeg_renderer"].render_instance_as_jpeg.return_value = b"jpeg"

        instance_result = handler.handle_instance(
            "1.2.3",
            "1.2.3.1",
            "1.2.3.1.1",
            request,
            "application/dicom",
            self.medmij_request_id,
        )
        rendered_result = handler.handle_instance_rendered(
            "1.2.3",
            "1.2.3.1",
            "1.2.3.1.1",
            request,
            "image/jpeg",
            self.medmij_request_id,
            1,
        )

        assert isinstance(instance_result, FileResponse)
        assert rendered_result.body == b"jpeg"
        assert (
            rendered_result.headers[MEDMIJ_REQUEST_ID_HEADER] == self.medmij_request_id
        )
