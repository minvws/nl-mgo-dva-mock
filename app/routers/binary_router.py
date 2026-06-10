from fastapi import APIRouter, Header, Request
from fastapi.responses import Response

from app.binary.services import BinaryRequestHandler
from app.config.models import AppConfig
from app.hcim.constants import MEDMIJ_REQUEST_ID_HEADER
from app.utils import resolve_instance

router = APIRouter()


@router.get("/{dataservice_id:int}/fhir/Binary/{binary_id:str}")
@router.get("/{dataservice_id:int}/fhir/Binary/{binary_id:str}/")
def get_binary(
    dataservice_id: int,
    binary_id: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    config: AppConfig = resolve_instance(AppConfig),
    binary_request_handler: BinaryRequestHandler = resolve_instance(
        BinaryRequestHandler
    ),
) -> Response:
    return binary_request_handler.get_binary(
        binary_id=binary_id,
        request=request,
        accept_header=accept_header,
        medmij_request_id=medmij_request_id,
    )
