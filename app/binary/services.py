import base64
import json

import inject
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from opentelemetry import trace

from app.binary.constants import DEFAULT_BINARY_RESOURCE_DIR_NAME
from app.binary.exceptions import (
    BinaryInvalidResourceError,
    BinaryResourceNotFoundError,
)
from app.binary.repositories import BinaryRepository
from app.binary.schemas import BinaryResource, BinaryRouteTarget
from app.config.models import AppConfig
from app.hcim.constants import (
    MEDMIJ_REQUEST_ID_HEADER,
    RESPONSE_CONTENT_TYPE_HEADER,
    WWW_AUTHENTICATE_HEADER,
)
from app.hcim.factories import OperationOutcomeFactory
from app.hcim.matchers import FhirVersionAcceptHeaderMatcher, HCIMResourceMatcher
from app.hcim.schemas import Code, OperationOutcome, Severity
from app.path import resource_dir


class BinaryMediaTypeMatcher:
    def accepts_media_type(
        self, accept_header: str | None, media_type: str | None
    ) -> bool:
        if accept_header is None or media_type is None:
            return False

        # if */* does not specifically request raw binary, server must return the FHIR representation
        accepted_media_ranges = self._accepted_media_ranges(accept_header)
        if media_type in accepted_media_ranges:
            return True

        top_level_wildcard = self._top_level_wildcard(media_type)
        return top_level_wildcard in accepted_media_ranges

    def _accepted_media_ranges(self, accept_header: str) -> set[str]:
        return {
            part.split(";")[0].strip()
            for part in accept_header.split(",")
            if part.strip()
        }

    def _top_level_wildcard(self, media_type: str) -> str:
        top_level = media_type.split("/", maxsplit=1)[0]
        return f"{top_level}/*"


class BinaryRouteResolver:
    @inject.autoparams("hcim_resource_matcher")
    def __init__(
        self, hcim_resource_matcher: HCIMResourceMatcher, use_demo_hcims: bool
    ) -> None:
        self._hcim_resource_matcher = hcim_resource_matcher
        self.__use_demo_hcims = use_demo_hcims

    def resolve(
        self,
        binary_id: str,
        request: Request,
    ) -> BinaryRouteTarget:
        path_prefix = "demo" if self.__use_demo_hcims else ""
        hcim_resource = self._hcim_resource_matcher.match_resource(request)

        if hcim_resource is None:
            return BinaryRouteTarget(
                resource_path=resource_dir(
                    path_prefix, DEFAULT_BINARY_RESOURCE_DIR_NAME, f"{binary_id}.json"
                ),
                expected_fhir_version=None,
            )

        return BinaryRouteTarget(
            resource_path=resource_dir(path_prefix, hcim_resource.resource_path),
            expected_fhir_version=hcim_resource.fhir_version,
        )


class BinaryResponseBuilder:
    def json_response(
        self,
        binary_resource: BinaryResource,
        medmij_request_id: str,
    ) -> JSONResponse:
        return JSONResponse(
            content=json.loads(binary_resource.raw_content),
            headers=self._headers(medmij_request_id, RESPONSE_CONTENT_TYPE_HEADER),
        )

    def raw_binary_response(
        self,
        binary_resource: BinaryResource,
        medmij_request_id: str,
    ) -> Response:
        if (
            binary_resource.content_type is None
            or binary_resource.payload_base64 is None
        ):
            raise BinaryInvalidResourceError(
                "Binary resource is missing contentType or base64 payload"
            )

        return Response(
            content=base64.b64decode(binary_resource.payload_base64),
            media_type=binary_resource.content_type,
            headers=self._headers(medmij_request_id),
        )

    def not_found_response(
        self, request: Request, medmij_request_id: str
    ) -> JSONResponse:
        return self.error_response(
            operation_outcome=OperationOutcomeFactory.with_issue(
                severity=Severity.ERROR,
                code=Code.NOT_FOUND,
                diagnostics=f"The resource {request.url} is not supported by the mock server",
            ),
            status_code=404,
            medmij_request_id=medmij_request_id,
        )

    def unsupported_representation_response(
        self,
        expected_fhir_version: str,
        binary_content_type: str,
        medmij_request_id: str,
    ) -> JSONResponse:
        return self.error_response(
            operation_outcome=OperationOutcomeFactory.with_issue(
                severity=Severity.ERROR,
                code=Code.NOT_SUPPORTED,
                diagnostics=(
                    "The requested representation is not supported. "
                    "Supported values: 'application/fhir+json; "
                    f"fhirVersion={expected_fhir_version}', '{binary_content_type}'"
                ),
            ),
            status_code=406,
            medmij_request_id=medmij_request_id,
        )

    def unsupported_fhir_version_response(
        self,
        request: Request,
        expected_fhir_version: str,
        medmij_request_id: str,
    ) -> JSONResponse:
        return self.error_response(
            operation_outcome=OperationOutcomeFactory.with_issue(
                severity=Severity.ERROR,
                code=Code.NOT_SUPPORTED,
                diagnostics=(
                    f"The 'Accept' header value: '{request.headers.get('accept')}' "
                    "is not supported. Supported value: "
                    f"'application/fhir+json; fhirVersion={expected_fhir_version}'"
                ),
            ),
            status_code=400,
            medmij_request_id=medmij_request_id,
            www_authenticate_error=(
                'error="invalid_request", error_description="Requested FHIR version not supported"'
            ),
        )

    def invalid_resource_response(self, medmij_request_id: str) -> JSONResponse:
        return self.error_response(
            operation_outcome=OperationOutcomeFactory.with_issue(
                severity=Severity.ERROR,
                code=Code.NOT_SUPPORTED,
                diagnostics="Binary resource is missing required fields (contentType or base64 payload)",
            ),
            status_code=500,
            medmij_request_id=medmij_request_id,
        )

    def error_response(
        self,
        operation_outcome: OperationOutcome,
        status_code: int,
        medmij_request_id: str,
        www_authenticate_error: str | None = None,
    ) -> JSONResponse:
        headers = self._headers(medmij_request_id, RESPONSE_CONTENT_TYPE_HEADER)
        if www_authenticate_error:
            headers[WWW_AUTHENTICATE_HEADER] = f"Bearer {www_authenticate_error}"

        return JSONResponse(
            content=operation_outcome.model_dump(),
            status_code=status_code,
            headers=headers,
        )

    def _headers(
        self,
        medmij_request_id: str,
        content_type: str | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}

        if content_type is not None:
            headers["Content-Type"] = content_type

        if medmij_request_id:
            headers[MEDMIJ_REQUEST_ID_HEADER] = medmij_request_id

        return headers


class BinaryRequestHandler:
    @inject.autoparams(
        "route_resolver",
        "repository",
        "media_type_matcher",
        "response_builder",
        "fhir_version_accept_header_matcher",
    )
    def __init__(
        self,
        route_resolver: BinaryRouteResolver,
        repository: BinaryRepository,
        media_type_matcher: BinaryMediaTypeMatcher,
        response_builder: BinaryResponseBuilder,
        fhir_version_accept_header_matcher: FhirVersionAcceptHeaderMatcher,
    ) -> None:
        self._route_resolver = route_resolver
        self._repository = repository
        self._media_type_matcher = media_type_matcher
        self._response_builder = response_builder
        self._fhir_version_accept_header_matcher = fhir_version_accept_header_matcher

    def get_binary(
        self,
        binary_id: str,
        request: Request,
        accept_header: str | None,
        medmij_request_id: str,
    ) -> Response:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("matching_request_to_binary_resource"):
            route_target = self._route_resolver.resolve(
                binary_id,
                request,
            )

            try:
                binary_resource = self._repository.load(
                    route_target.resource_path,
                )
            except BinaryResourceNotFoundError:
                return self._response_builder.not_found_response(
                    request, medmij_request_id
                )
            except BinaryInvalidResourceError:
                return self._response_builder.invalid_resource_response(
                    medmij_request_id
                )

            if self._media_type_matcher.accepts_media_type(
                accept_header, binary_resource.content_type
            ):
                try:
                    return self._response_builder.raw_binary_response(
                        binary_resource, medmij_request_id
                    )
                except BinaryInvalidResourceError:
                    return self._response_builder.invalid_resource_response(
                        medmij_request_id
                    )

            if (
                accept_header is not None
                and route_target.expected_fhir_version is not None
                and not self._fhir_version_accept_header_matcher.fhir_version_matches(
                    accept_header, route_target.expected_fhir_version
                )
            ):
                if binary_resource.content_type is not None:
                    return self._response_builder.unsupported_representation_response(
                        route_target.expected_fhir_version,
                        binary_resource.content_type,
                        medmij_request_id,
                    )

                return self._response_builder.unsupported_fhir_version_response(
                    request,
                    route_target.expected_fhir_version,
                    medmij_request_id,
                )

            return self._response_builder.json_response(
                binary_resource, medmij_request_id
            )
