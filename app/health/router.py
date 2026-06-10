from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.health.models import HealthResponse
from app.health.services import HealthService
from app.utils import resolve_instance

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(
    health_service: HealthService = resolve_instance(HealthService),
) -> Response:
    health_response = health_service.get_health()
    status_code = 200 if health_response.healthy else 503

    return JSONResponse(
        content=health_response.model_dump(),
        status_code=status_code,
    )
