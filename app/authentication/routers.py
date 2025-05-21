import uuid

from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import JSONResponse

from app.config.models import AppConfig
from app.utils import resolve_instance

from .exceptions import AuthorizationHttpException
from .responses import AuthenticationRedirectResponse
from .schemas import TokenRequestModel
from .services import (
    AuthenticationMock,
    MedMijAuthCallbackUrlDirector,
)

router = APIRouter(
    tags=["authentication"],
)


@router.get("/auth")
def authenticate(
    redirect_uri: str = Query(..., min_length=1),
    scope: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
    correlation_id: str = Query(..., alias="X-Correlation-ID", min_length=1),
    medmij_id: str = Query(..., alias="MedMij-Request-ID", min_length=1),
    authenticator: AuthenticationMock = resolve_instance(AuthenticationMock),
    director: MedMijAuthCallbackUrlDirector = resolve_instance(
        MedMijAuthCallbackUrlDirector
    ),
) -> Response:
    try:
        code: str = authenticator.authenticate(scope=scope)
    except AuthorizationHttpException as e:
        return AuthenticationRedirectResponse(
            redirect_url=f"{redirect_uri}?error=401&error_description=Authentication failed.&state=xyz"
        )

    url: str = director.build_callback_url(
        callback_uri=redirect_uri, state=state, code=code
    )

    return AuthenticationRedirectResponse(redirect_url=url)


@router.post("/token")
def get_access_token(
    request: TokenRequestModel,
    correlation_id: str = Header(..., alias="X-Correlation-ID", min_length=1),
    medmij_id: str = Header(..., alias="MedMij-Request-ID", min_length=1),
    config: AppConfig = resolve_instance(AppConfig),
) -> JSONResponse:
    return JSONResponse(
        {
            "access_token": str(uuid.uuid4()),
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": str(uuid.uuid4()),
            "scope": "48 49 51 63",  # supported dataservices for the mock dva
        }
    )
