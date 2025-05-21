import json
from typing import List

from fastapi import APIRouter, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.config.models import AppConfig
from app.hcim.constants import (
    MEDMIJ_REQUEST_ID_HEADER,
    RESPONSE_CONTENT_TYPE_HEADER,
    WWW_AUTHENTICATE_HEADER,
)
from app.hcim.factories import OperationOutcomeFactory
from app.hcim.matchers import HCIMResourceMatch, HCIMResourceMatcher
from app.hcim.schemas import Code, OperationOutcome, Severity
from app.hcim.services import FhirVersionAcceptHeaderMatcher
from app.path import resource_dir
from app.utils import resolve_instance
from fhir.models import Resource
from fhir.scanner import ResourceScanner

router = APIRouter()


@router.get("/fhir/resources", response_model=List[Resource])
def list_resources(
    resource_scanner: ResourceScanner = resolve_instance(ResourceScanner),
) -> List[Resource]:
    return resource_scanner.scan()


@router.get("/{dataservice_id:int}/fhir/{resource:str}/{id:str}")
@router.get("/{dataservice_id:int}/fhir/{resource:str}/{id:str}/")
def show(
    dataservice_id: int,
    resource: str,
    id: str,
    request: Request,
    config: AppConfig = resolve_instance(AppConfig),
    hcim_resource_matcher: HCIMResourceMatcher = resolve_instance(HCIMResourceMatcher),
    accept_header: str = Header(None, alias="Accept"),
) -> JSONResponse:
    return __handle_request(
        config, hcim_resource_matcher, resource, id, request, accept_header
    )


@router.get("/{dataservice_id:int}/fhir/{resource:str}")
@router.get("/{dataservice_id:int}/fhir/{resource:str}/")
def index(
    dataservice_id: int,
    resource: str,
    request: Request,
    config: AppConfig = resolve_instance(AppConfig),
    hcim_resource_matcher: HCIMResourceMatcher = resolve_instance(HCIMResourceMatcher),
    accept_header: str = Header(None, alias="Accept"),
) -> JSONResponse:
    return __handle_request(
        config, hcim_resource_matcher, resource, None, request, accept_header
    )


def __handle_request(
    config: AppConfig,
    hcim_resource_matcher: HCIMResourceMatcher,
    resource: str,
    id: str | None,
    request: Request,
    accept_header: str,
) -> JSONResponse:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("matching_request_to_resource"):
        path_prefix = "demo" if config.use_demo_hcims else ""
        medmij_request_id = request.headers.get(MEDMIJ_REQUEST_ID_HEADER)

        hcim_resource: HCIMResourceMatch | None = hcim_resource_matcher.match_resource(
            request
        )

        if (
            hcim_resource is not None
            and not FhirVersionAcceptHeaderMatcher().fhir_version_matches(
                accept_header, hcim_resource.fhir_version
            )
        ):
            return __error_response(
                OperationOutcomeFactory.with_issue(
                    severity=Severity.ERROR,
                    code=Code.NOT_SUPPORTED,
                    diagnostics=f"The 'Accept' header value: '{request.headers.get('accept')}' is not supported. Supported value: 'application/fhir+json; fhirVersion={hcim_resource.fhir_version}'",
                ),
                status_code=400,
                medmij_request_id=medmij_request_id,
                www_authenticate_error='error="invalid_request", error_description="Requested FHIR version not supported"',
            )

        if hcim_resource is None:
            if id is None:
                return __error_response(
                    OperationOutcomeFactory.with_issue(
                        severity=Severity.ERROR,
                        code=Code.NOT_FOUND,
                        diagnostics=f"The resource {request.url} is not supported by the mock server",
                    ),
                    status_code=404,
                    medmij_request_id=medmij_request_id,
                )
            else:
                resource_path = resource_dir(path_prefix, f"{resource}", f"{id}.json")
        else:
            resource_path = resource_dir(path_prefix, hcim_resource.resource_path)

        try:
            with open(resource_path) as file:
                contents = file.read().replace("{{BASE_URL}}", config.base_url)
                data = jsonable_encoder(json.loads(contents))
                headers = headers = {"Content-Type": RESPONSE_CONTENT_TYPE_HEADER}

                if medmij_request_id:
                    headers[MEDMIJ_REQUEST_ID_HEADER] = medmij_request_id

                return JSONResponse(
                    content=data,
                    headers=headers,
                )
        except FileNotFoundError:
            return __error_response(
                OperationOutcomeFactory.with_issue(
                    severity=Severity.ERROR,
                    code=Code.NOT_FOUND,
                    diagnostics=f"The resource {request.url} is not supported by the mock server",
                ),
                status_code=404,
                medmij_request_id=medmij_request_id,
            )


def __error_response(
    operation_outcome: OperationOutcome,
    status_code: int,
    medmij_request_id: str | None,
    www_authenticate_error: str | None = None,
) -> JSONResponse:
    headers = headers = {"Content-Type": RESPONSE_CONTENT_TYPE_HEADER}

    if medmij_request_id:
        headers[MEDMIJ_REQUEST_ID_HEADER] = medmij_request_id

    if www_authenticate_error:
        headers[WWW_AUTHENTICATE_HEADER] = f"Bearer {www_authenticate_error}"

    return JSONResponse(
        content=operation_outcome.model_dump(),
        status_code=status_code,
        headers=headers,
    )
