from collections import defaultdict
from collections.abc import Callable
from io import BytesIO
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import inject
import numpy as np
import pydicom
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image

from pydicom.uid import UID

from app.dicom.constants import (
    DICOM_JSON_MEDIA_TYPES,
    DICOM_MEDIA_TYPES,
    JPEG_MEDIA_TYPES,
    MULTIPART_DICOM_MEDIA_TYPES,
)
from app.dicom.exceptions import (
    DicomFrameNotFoundError,
    DicomNotFoundError,
    DicomRenderingError,
    DicomRepresentationNotSupportedError,
)
from app.dicom.repositories import DicomRepository
from app.dicom.schemas import DicomInstance, MultipartDicomPayload
from app.hcim.constants import MEDMIJ_REQUEST_ID_HEADER


class DicomAcceptHeaderValidator:
    def validate_supported_media_types(
        self, accept_header: str | None, supported_media_types: set[str]
    ) -> None:
        if accept_header is None:
            return

        if any(
            self.header_accepts_media_type(accept_header, media_type)
            for media_type in supported_media_types
        ):
            return

        raise DicomRepresentationNotSupportedError(supported_media_types)

    def header_accepts_media_type(
        self, accept_header: str | None, media_type: str
    ) -> bool:
        if accept_header is None:
            return False

        accepted_values = {
            part.split(";")[0].strip()
            for part in accept_header.split(",")
            if part.strip()
        }
        top_level = media_type.split("/", maxsplit=1)[0]
        return (
            "*/*" in accepted_values
            or media_type in accepted_values
            or f"{top_level}/*" in accepted_values
        )


class DicomMetadataBuilder:
    def build_series_manifest(
        self,
        study_uid: str,
        study_instances: tuple[DicomInstance, ...],
        series_url_resolver: Callable[[str], str],
    ) -> list[dict[str, Any]]:
        grouped_instances: defaultdict[str, list[DicomInstance]] = defaultdict(list)
        for instance in study_instances:
            grouped_instances[instance.series_uid].append(instance)

        series_entries: list[dict[str, Any]] = []
        for series_uid in sorted(grouped_instances):
            representative_instance = sorted(
                grouped_instances[series_uid], key=lambda item: item.instance_uid
            )[0]
            series_entries.append(
                {
                    "0020000D": {"vr": "UI", "Value": [study_uid]},
                    "0020000E": {"vr": "UI", "Value": [series_uid]},
                    "00080060": {
                        "vr": "CS",
                        "Value": [representative_instance.modality],
                    },
                    "00081030": {
                        "vr": "LO",
                        "Value": [representative_instance.study_description or ""],
                    },
                    "0008103E": {
                        "vr": "LO",
                        "Value": [representative_instance.series_description or ""],
                    },
                    "00081190": {
                        "vr": "UR",
                        "Value": [series_url_resolver(series_uid)],
                    },
                }
            )

        return series_entries

    def build_instance_metadata(
        self, instances: tuple[DicomInstance, ...]
    ) -> list[dict[str, Any]]:
        instance_entries: list[dict[str, Any]] = []
        for instance in instances:
            entry: dict[str, Any] = {
                "0020000D": {"vr": "UI", "Value": [instance.study_uid]},
                "0020000E": {"vr": "UI", "Value": [instance.series_uid]},
                "00080018": {"vr": "UI", "Value": [instance.instance_uid]},
                "00080016": {"vr": "UI", "Value": [instance.sop_class_uid]},
                "00080060": {"vr": "CS", "Value": [instance.modality]},
                "00081030": {"vr": "LO", "Value": [instance.study_description or ""]},
                "0008103E": {"vr": "LO", "Value": [instance.series_description or ""]},
            }
            if instance.body_part_examined:
                entry["00180015"] = {
                    "vr": "CS",
                    "Value": [instance.body_part_examined],
                }
            if instance.number_of_frames > 1:
                entry["00280008"] = {
                    "vr": "IS",
                    "Value": [str(instance.number_of_frames)],
                }
            instance_entries.append(entry)

        return instance_entries


class DicomManifestBuilder:
    def build_multipart_payload(
        self,
        instances: tuple[DicomInstance, ...],
        content_location_resolver: Callable[[DicomInstance], str],
    ) -> MultipartDicomPayload:
        boundary = (
            "mock-boundary-"
            f"{self._stable_uid(':'.join(instance.instance_uid for instance in instances))}"
        )
        payload = bytearray()
        for instance in instances:
            payload.extend(f"--{boundary}\r\n".encode())
            payload.extend(b"Content-Type: application/dicom\r\n")
            payload.extend(
                f"Content-Location: {content_location_resolver(instance)}\r\n\r\n".encode()
            )
            payload.extend(instance.path.read_bytes())
            payload.extend(b"\r\n")
        payload.extend(f"--{boundary}--\r\n".encode())
        return MultipartDicomPayload(boundary=boundary, content=bytes(payload))

    @staticmethod
    def _stable_uid(seed: str) -> UID:
        return UID(f"2.25.{uuid5(NAMESPACE_URL, seed).int}")


class DicomJpegRenderer:
    @inject.autoparams("repository")
    def __init__(self, repository: DicomRepository) -> None:
        self._repository = repository

    def render_instance_as_jpeg(
        self, instance: DicomInstance, frame_id: int | None
    ) -> bytes:
        dataset = self._repository.read_dataset(instance)
        frame_number = frame_id or 1

        if frame_number < 1:
            raise DicomFrameNotFoundError("Frame ids start at 1")

        if frame_number > instance.number_of_frames:
            raise DicomFrameNotFoundError(
                f"The frame '{frame_number}' is not available for DICOM instance "
                f"'{instance.instance_uid}'"
            )

        pixel_array = dataset.pixel_array
        if instance.number_of_frames > 1:
            pixel_array = pixel_array[frame_number - 1]
        elif frame_id not in (None, 1):
            raise DicomFrameNotFoundError(
                f"The frame '{frame_number}' is not available for DICOM instance "
                f"'{instance.instance_uid}'"
            )

        image = self._image_from_pixel_array(
            pixel_array, str(getattr(dataset, "PhotometricInterpretation", ""))
        )
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        return buffer.getvalue()

    def _image_from_pixel_array(
        self, pixel_array: Any, photometric_interpretation: str
    ) -> Image.Image:
        if getattr(pixel_array, "ndim", 0) == 2:
            normalized = self._normalize_to_uint8(pixel_array)
            if photometric_interpretation == "MONOCHROME1":
                normalized = 255 - normalized
            return Image.fromarray(normalized, mode="L")

        if getattr(pixel_array, "ndim", 0) == 3:
            normalized = self._normalize_to_uint8(pixel_array)
            return Image.fromarray(normalized)

        raise DicomRenderingError("The DICOM pixel data could not be rendered as JPEG")

    @staticmethod
    def _normalize_to_uint8(pixel_array: Any) -> np.ndarray[Any, Any]:
        array = np.asarray(pixel_array, dtype=np.float32)
        minimum = float(array.min())
        maximum = float(array.max())

        if minimum == maximum:
            return np.zeros(array.shape, dtype=np.uint8)

        normalized = (array - minimum) / (maximum - minimum)
        return (normalized * 255).astype(np.uint8)


class DicomRouteHandler:
    @inject.autoparams(
        "repository",
        "accept_validator",
        "metadata_builder",
        "manifest_builder",
        "jpeg_renderer",
    )
    def __init__(
        self,
        repository: DicomRepository,
        accept_validator: DicomAcceptHeaderValidator,
        metadata_builder: DicomMetadataBuilder,
        manifest_builder: DicomManifestBuilder,
        jpeg_renderer: DicomJpegRenderer,
    ) -> None:
        self._repository = repository
        self._accept_validator = accept_validator
        self._metadata_builder = metadata_builder
        self._manifest_builder = manifest_builder
        self._jpeg_renderer = jpeg_renderer

    def handle_dicom(
        self,
        document_id: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> FileResponse:
        self._accept_validator.validate_supported_media_types(
            accept_header, DICOM_MEDIA_TYPES
        )
        instance = self._repository.get_instance_by_document_id(document_id)
        return self._dicom_file_response(instance, medmij_request_id)

    def handle_study_series_manifest(
        self,
        study_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> Response:
        # series list endpoint returns JSON metadata only.
        self._accept_validator.validate_supported_media_types(
            accept_header, DICOM_JSON_MEDIA_TYPES
        )
        study_instances = self._repository.get_study_instances(study_uid)

        series_entries = self._metadata_builder.build_series_manifest(
            study_uid=study_uid,
            study_instances=study_instances,
            series_url_resolver=lambda series_uid: self._absolute_url(
                request, f"/9000002/wado/studies/{study_uid}/series/{series_uid}"
            ),
        )

        return JSONResponse(
            content=series_entries,
            media_type="application/dicom+json",
            headers=self._response_headers(medmij_request_id),
        )

    def handle_study_metadata(
        self,
        study_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> Response:
        # Metadata Resource payload contains all instance attributes; application/dicom is not a valid Accept here.
        self._accept_validator.validate_supported_media_types(
            accept_header, DICOM_JSON_MEDIA_TYPES
        )
        study_instances = self._repository.get_study_instances(study_uid)

        return JSONResponse(
            content=self._metadata_builder.build_instance_metadata(study_instances),
            media_type="application/dicom+json",
            headers=self._response_headers(medmij_request_id),
        )

    def handle_study(
        self,
        study_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> Response:
        self._accept_validator.validate_supported_media_types(
            accept_header, MULTIPART_DICOM_MEDIA_TYPES
        )
        study_instances = self._repository.get_study_instances(study_uid)
        return self._multipart_dicom_response(
            study_instances, request, medmij_request_id
        )

    def handle_series(
        self,
        study_uid: str,
        series_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> Response:
        self._accept_validator.validate_supported_media_types(
            accept_header, MULTIPART_DICOM_MEDIA_TYPES
        )
        series_instances = self._repository.get_series_instances(study_uid, series_uid)
        return self._multipart_dicom_response(
            series_instances, request, medmij_request_id
        )

    def handle_series_metadata(
        self,
        study_uid: str,
        series_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> JSONResponse:
        self._accept_validator.validate_supported_media_types(
            accept_header, DICOM_JSON_MEDIA_TYPES
        )
        series_instances = self._repository.get_series_instances(study_uid, series_uid)
        return JSONResponse(
            content=self._metadata_builder.build_instance_metadata(series_instances),
            media_type="application/dicom+json",
            headers=self._response_headers(medmij_request_id),
        )

    def handle_instance(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> FileResponse:
        self._accept_validator.validate_supported_media_types(
            accept_header, DICOM_MEDIA_TYPES
        )
        instance = self._repository.get_instance_by_uids(
            study_uid, series_uid, instance_uid
        )
        return self._dicom_file_response(instance, medmij_request_id)

    def handle_instance_rendered(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
        frame_id: int | None = None,
    ) -> Response:
        self._accept_validator.validate_supported_media_types(
            accept_header, JPEG_MEDIA_TYPES
        )
        instance = self._repository.get_instance_by_uids(
            study_uid, series_uid, instance_uid
        )
        rendered_bytes = self._jpeg_renderer.render_instance_as_jpeg(instance, frame_id)
        return Response(
            content=rendered_bytes,
            media_type="image/jpeg",
            headers=self._response_headers(medmij_request_id),
        )

    def _dicom_file_response(
        self, instance: DicomInstance, medmij_request_id: str
    ) -> FileResponse:
        if not instance.path.exists():
            raise DicomNotFoundError(
                f"The DICOM file '{instance.document_id}' is not available on disk"
            )

        return FileResponse(
            path=instance.path,
            media_type="application/dicom",
            filename=instance.path.name,
            headers=self._response_headers(medmij_request_id),
        )

    def _multipart_dicom_response(
        self,
        instances: tuple[DicomInstance, ...],
        request: Request,
        medmij_request_id: str,
    ) -> Response:
        payload = self._manifest_builder.build_multipart_payload(
            instances=instances,
            content_location_resolver=lambda instance: self._absolute_url(
                request, self._instance_path(instance)
            ),
        )
        headers = self._response_headers(medmij_request_id)
        headers["Content-Type"] = (
            'multipart/related; type="application/dicom"; '
            f'boundary="{payload.boundary}"'
        )
        return Response(content=payload.content, headers=headers)

    @staticmethod
    def _absolute_url(request: Request, path: str) -> str:
        return f"{str(request.base_url).rstrip('/')}{path}"

    @staticmethod
    def _instance_path(instance: DicomInstance) -> str:
        return (
            f"/9000002/wado/studies/{instance.study_uid}/series/"
            f"{instance.series_uid}/instances/{instance.instance_uid}"
        )

    @staticmethod
    def _response_headers(medmij_request_id: str) -> dict[str, str]:
        return {MEDMIJ_REQUEST_ID_HEADER: medmij_request_id}
