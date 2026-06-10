import base64
from typing import cast

import pytest
from fastapi import Request
from fastapi.responses import Response
from pytest_mock import MockerFixture, MockType
from starlette.types import Scope

from app.binary.exceptions import (
    BinaryInvalidResourceError,
    BinaryResourceNotFoundError,
)
from app.binary.repositories import BinaryRepository
from app.binary.schemas import BinaryResource, BinaryRouteTarget
from app.binary.services import (
    BinaryMediaTypeMatcher,
    BinaryRequestHandler,
    BinaryResponseBuilder,
    BinaryRouteResolver,
)
from app.config.models import AppConfig, OAuthConfig, TelemetryConfig
from app.hcim.constants import (
    MEDMIJ_REQUEST_ID_HEADER,
    RESPONSE_CONTENT_TYPE_HEADER,
    WWW_AUTHENTICATE_HEADER,
)
from app.hcim.factories import OperationOutcomeFactory
from app.hcim.matchers import FhirVersionAcceptHeaderMatcher
from app.hcim.schemas import Code, Severity
from app.path import resource_dir


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
        "server": ("localhost", 80),
        "client": ("testclient", 50000),
        "root_path": "",
    }
    return Request(scope)


def response_text(response: Response) -> str:
    body = response.body
    if isinstance(body, memoryview):
        return body.tobytes().decode()
    return body.decode()


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig(
        base_url="http://localhost",
        use_demo_hcims=False,
        oauth=OAuthConfig(),
        telemetry=TelemetryConfig(
            enabled=False,
            service_name="mock",
            collector_grpc_url="",
        ),
    )


@pytest.fixture
def mocked_request() -> Request:
    return build_request("/fhir/Binary/test")


@pytest.fixture
def binary_response_builder() -> BinaryResponseBuilder:
    return BinaryResponseBuilder()


@pytest.fixture
def binary_resource() -> BinaryResource:
    return BinaryResource(
        raw_content='{"resourceType": "Binary"}',
        content_type="application/pdf",
        payload_base64=base64.b64encode(b"pdf-content").decode(),
    )


class TestBinaryMediaTypeMatcher:
    @pytest.mark.parametrize(
        ("accept_header", "media_type"),
        [
            ("application/pdf", "application/pdf"),
            ("application/*", "application/pdf"),
            ("application/pdf;q=0.9", "application/pdf"),
            ("text/html, application/pdf", "application/pdf"),
        ],
    )
    def test_accepts_media_type(self, accept_header: str, media_type: str) -> None:
        assert (
            BinaryMediaTypeMatcher().accepts_media_type(accept_header, media_type)
            is True
        )

    @pytest.mark.parametrize(
        ("accept_header", "media_type"),
        [
            ("text/plain", "application/pdf"),
            (None, "application/pdf"),
            ("application/pdf", None),
            (None, None),
            # */* does not specifically request raw binary. the server must return FHIR JSON.
            ("*/*", "application/pdf"),
        ],
    )
    def test_rejects_media_type(
        self,
        accept_header: str | None,
        media_type: str | None,
    ) -> None:
        assert (
            BinaryMediaTypeMatcher().accepts_media_type(accept_header, media_type)
            is False
        )

    def test_parses_accept_ranges_without_quality_values(self) -> None:
        assert BinaryMediaTypeMatcher()._accepted_media_ranges(
            "text/html;q=0.9, application/json;q=0.8"
        ) == {"text/html", "application/json"}

    def test_builds_top_level_wildcard(self) -> None:
        assert (
            BinaryMediaTypeMatcher()._top_level_wildcard("application/fhir+json")
            == "application/*"
        )


class TestBinaryRouteResolver:
    def test_resolve_uses_hcim_match(
        self, mocker: MockerFixture, app_config: AppConfig
    ) -> None:
        matcher = mocker.Mock()
        matcher.match_resource.return_value = mocker.Mock(
            resource_path="Patient/nl-core-patient-01",
            fhir_version="3.0",
        )

        result = BinaryRouteResolver(matcher, app_config.use_demo_hcims).resolve(
            "binary-id",
            mocker.Mock(spec=Request),
        )

        assert result == BinaryRouteTarget(
            resource_path=resource_dir("Patient/nl-core-patient-01"),
            expected_fhir_version="3.0",
        )

    @pytest.mark.parametrize("use_demo_hcims", [False, True])
    def test_resolve_falls_back_to_default_binary_resource(
        self,
        mocker: MockerFixture,
        app_config: AppConfig,
        use_demo_hcims: bool,
    ) -> None:
        matcher = mocker.Mock()
        matcher.match_resource.return_value = None
        app_config.use_demo_hcims = use_demo_hcims

        result = BinaryRouteResolver(matcher, app_config.use_demo_hcims).resolve(
            "binary-id",
            mocker.Mock(spec=Request),
        )

        expected_prefix = "demo" if use_demo_hcims else ""
        assert result == BinaryRouteTarget(
            resource_path=resource_dir(expected_prefix, "Binary", "binary-id.json"),
            expected_fhir_version=None,
        )


class TestBinaryResponseBuilder:
    @pytest.fixture(autouse=True)
    def _set_medmij_request_id(self, medmij_request_id: str) -> None:
        self.medmij_request_id = medmij_request_id

    def test_json_response_sets_fhir_content_type(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        response = binary_response_builder.json_response(
            BinaryResource(
                raw_content='{"id": "test"}',
                content_type="application/json",
                payload_base64="",
            ),
            self.medmij_request_id,
        )

        assert response.status_code == 200
        assert response.headers["Content-Type"] == RESPONSE_CONTENT_TYPE_HEADER
        assert response.headers[MEDMIJ_REQUEST_ID_HEADER] == self.medmij_request_id

    def test_json_response_omits_empty_request_id(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        response = binary_response_builder.json_response(
            BinaryResource(
                raw_content='{"id": "test"}',
                content_type="application/json",
                payload_base64="",
            ),
            "",
        )

        assert MEDMIJ_REQUEST_ID_HEADER not in response.headers

    def test_raw_binary_response_decodes_payload(
        self,
        binary_response_builder: BinaryResponseBuilder,
        binary_resource: BinaryResource,
    ) -> None:
        response = binary_response_builder.raw_binary_response(
            binary_resource, self.medmij_request_id
        )

        assert response.body == b"pdf-content"
        assert response.media_type == "application/pdf"
        assert response.headers[MEDMIJ_REQUEST_ID_HEADER] == self.medmij_request_id

    @pytest.mark.parametrize(
        "resource",
        [
            BinaryResource(
                raw_content="{}",
                content_type=None,  # type: ignore[arg-type]
                payload_base64="payload",
            ),
            BinaryResource(
                raw_content="{}",
                content_type="application/pdf",
                payload_base64=None,  # type: ignore
            ),
        ],
    )
    def test_raw_binary_response_requires_content_type_and_payload(
        self,
        binary_response_builder: BinaryResponseBuilder,
        resource: BinaryResource,
    ) -> None:
        with pytest.raises(BinaryInvalidResourceError):
            binary_response_builder.raw_binary_response(
                resource, self.medmij_request_id
            )

    def test_not_found_response_wraps_operation_outcome(
        self,
        binary_response_builder: BinaryResponseBuilder,
        mocked_request: Request,
    ) -> None:
        response = binary_response_builder.not_found_response(
            mocked_request, self.medmij_request_id
        )

        assert response.status_code == 404
        assert response.headers[MEDMIJ_REQUEST_ID_HEADER] == self.medmij_request_id
        assert "not supported by the mock server" in response_text(response)

    def test_unsupported_representation_response_describes_supported_types(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        response = binary_response_builder.unsupported_representation_response(
            "4.0",
            "application/pdf",
            self.medmij_request_id,
        )

        assert response.status_code == 406
        assert "application/pdf" in response_text(response)

    def test_unsupported_fhir_version_response_adds_www_authenticate_header(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        request = build_request(
            "/fhir/Binary/test",
            {"accept": "application/fhir+json; fhirVersion=3.0"},
        )

        response = binary_response_builder.unsupported_fhir_version_response(
            request,
            "4.0",
            self.medmij_request_id,
        )

        assert response.status_code == 400
        assert WWW_AUTHENTICATE_HEADER in response.headers

    def test_invalid_resource_response_returns_500_with_error_diagnostics(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        response = binary_response_builder.invalid_resource_response(
            self.medmij_request_id
        )

        assert response.status_code == 500
        assert response.headers[MEDMIJ_REQUEST_ID_HEADER] == self.medmij_request_id
        assert "missing required fields" in response_text(response)

    def test_error_response_adds_www_authenticate_header_when_requested(
        self,
        binary_response_builder: BinaryResponseBuilder,
    ) -> None:
        operation_outcome = OperationOutcomeFactory.with_issue(
            severity=Severity.ERROR,
            code=Code.NOT_FOUND,
            diagnostics="test error",
        )

        response = binary_response_builder.error_response(
            operation_outcome,
            404,
            self.medmij_request_id,
            'error="not_found"',
        )

        assert response.status_code == 404
        assert response.headers[WWW_AUTHENTICATE_HEADER] == 'Bearer error="not_found"'


@pytest.fixture
def route_resolver(mocker: MockerFixture) -> MockType:
    mock: MockType = mocker.Mock()
    return mock


@pytest.fixture
def repository(mocker: MockerFixture) -> MockType:
    mock: MockType = mocker.Mock()
    return mock


@pytest.fixture
def media_type_matcher(mocker: MockerFixture) -> MockType:
    mock: MockType = mocker.Mock()
    return mock


@pytest.fixture
def response_builder(mocker: MockerFixture) -> MockType:
    mock: MockType = mocker.Mock()
    return mock


@pytest.fixture
def fhir_version_matcher(
    mocker: MockerFixture,
) -> MockType:
    mock: MockType = mocker.Mock()
    return mock


@pytest.fixture
def request_handler(
    route_resolver: MockType,
    repository: MockType,
    media_type_matcher: MockType,
    response_builder: MockType,
    fhir_version_matcher: MockType,
) -> BinaryRequestHandler:
    handler: BinaryRequestHandler = BinaryRequestHandler(
        route_resolver=cast(BinaryRouteResolver, route_resolver),
        repository=cast(BinaryRepository, repository),
        media_type_matcher=cast(BinaryMediaTypeMatcher, media_type_matcher),
        response_builder=cast(BinaryResponseBuilder, response_builder),
        fhir_version_accept_header_matcher=cast(
            FhirVersionAcceptHeaderMatcher,
            fhir_version_matcher,
        ),
    )
    return handler


class TestBinaryRequestHandler:
    @pytest.fixture(autouse=True)
    def _set_medmij_request_id(self, medmij_request_id: str) -> None:
        self.medmij_request_id = medmij_request_id

    def test_get_binary_returns_not_found_response_when_resource_is_missing(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        response_builder: MockType,
        mocked_request: Request,
    ) -> None:
        route_resolver.resolve.return_value = BinaryRouteTarget("/missing.json", None)
        repository.load.side_effect = BinaryResourceNotFoundError("missing")

        result = request_handler.get_binary(
            "binary-id", mocked_request, None, self.medmij_request_id
        )

        assert result is response_builder.not_found_response.return_value

    def test_get_binary_returns_invalid_resource_response_when_repository_load_is_invalid(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        response_builder: MockType,
    ) -> None:
        request = build_request(
            "/fhir/Binary/test", {MEDMIJ_REQUEST_ID_HEADER: self.medmij_request_id}
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", None)
        repository.load.side_effect = BinaryInvalidResourceError(
            "Binary payload is invalid"
        )

        result = request_handler.get_binary(
            "binary-id", request, "application/pdf", self.medmij_request_id
        )

        assert result is response_builder.invalid_resource_response.return_value
        response_builder.invalid_resource_response.assert_called_once_with(
            self.medmij_request_id
        )

    def test_get_binary_returns_raw_binary_when_media_type_matches(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        media_type_matcher: MockType,
        response_builder: MockType,
        binary_resource: BinaryResource,
    ) -> None:
        request = build_request(
            "/fhir/Binary/test", {MEDMIJ_REQUEST_ID_HEADER: self.medmij_request_id}
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", None)
        repository.load.return_value = binary_resource
        media_type_matcher.accepts_media_type.return_value = True

        result = request_handler.get_binary(
            "binary-id", request, "application/pdf", self.medmij_request_id
        )

        assert result is response_builder.raw_binary_response.return_value
        response_builder.raw_binary_response.assert_called_once_with(
            binary_resource,
            self.medmij_request_id,
        )

    def test_get_binary_returns_json_when_fhir_version_matches(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        media_type_matcher: MockType,
        response_builder: MockType,
        fhir_version_matcher: MockType,
        mocked_request: Request,
    ) -> None:
        resource = BinaryResource(
            raw_content='{"resourceType": "Binary"}',
            content_type=None,  # type: ignore
            payload_base64=None,  # type: ignore
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", "3.0")
        repository.load.return_value = resource
        media_type_matcher.accepts_media_type.return_value = False
        fhir_version_matcher.fhir_version_matches.return_value = True

        result = request_handler.get_binary(
            "binary-id",
            mocked_request,
            "application/fhir+json; fhirVersion=3.0",
            self.medmij_request_id,
        )

        assert result is response_builder.json_response.return_value

    def test_get_binary_returns_unsupported_representation_when_binary_has_native_media_type(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        media_type_matcher: MockType,
        response_builder: MockType,
        fhir_version_matcher: MockType,
        mocked_request: Request,
    ) -> None:
        resource = BinaryResource(
            raw_content="{}", content_type="application/pdf", payload_base64="payload"
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", "3.0")
        repository.load.return_value = resource
        media_type_matcher.accepts_media_type.return_value = False
        fhir_version_matcher.fhir_version_matches.return_value = False

        result = request_handler.get_binary(
            "binary-id", mocked_request, "image/jpeg", self.medmij_request_id
        )

        assert (
            result is response_builder.unsupported_representation_response.return_value
        )

    def test_get_binary_returns_unsupported_fhir_version_when_binary_has_no_native_media_type(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        media_type_matcher: MockType,
        response_builder: MockType,
        fhir_version_matcher: MockType,
    ) -> None:
        request = build_request(
            "/fhir/Binary/test", {"accept": "application/fhir+json; fhirVersion=3.0"}
        )
        resource = BinaryResource(
            raw_content="{}",
            content_type=None,  # type: ignore
            payload_base64=None,  # type: ignore
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", "4.0")
        repository.load.return_value = resource
        media_type_matcher.accepts_media_type.return_value = False
        fhir_version_matcher.fhir_version_matches.return_value = False

        result = request_handler.get_binary(
            "binary-id",
            request,
            "application/fhir+json; fhirVersion=3.0",
            self.medmij_request_id,
        )

        assert result is response_builder.unsupported_fhir_version_response.return_value

    def test_get_binary_returns_invalid_resource_response_when_payload_is_invalid(
        self,
        request_handler: BinaryRequestHandler,
        route_resolver: MockType,
        repository: MockType,
        media_type_matcher: MockType,
        response_builder: MockType,
    ) -> None:
        request = build_request(
            "/fhir/Binary/test", {MEDMIJ_REQUEST_ID_HEADER: self.medmij_request_id}
        )
        resource = BinaryResource(
            raw_content="{}",
            content_type="application/pdf",
            payload_base64=None,  # type: ignore
        )
        route_resolver.resolve.return_value = BinaryRouteTarget("/binary.json", None)
        repository.load.return_value = resource
        media_type_matcher.accepts_media_type.return_value = True
        response_builder.raw_binary_response.side_effect = BinaryInvalidResourceError(
            "Binary resource is missing contentType or base64 payload"
        )

        result = request_handler.get_binary(
            "binary-id", request, "application/pdf", self.medmij_request_id
        )

        assert result is response_builder.invalid_resource_response.return_value
        response_builder.invalid_resource_response.assert_called_once_with(
            self.medmij_request_id
        )
