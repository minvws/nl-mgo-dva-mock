import inject
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .authentication.routers import router as auth_mock_router
from .bindings import configure_bindings
from .config.models import AppConfig
from .constants import APP_NAME
from .dicom.exceptions import register_exception_handlers
from .health.router import router as health_router
from .routers.binary_router import router as binary_router
from .routers.dicom_router import router as dicom_router
from .routers.docs_router import router as docs_router
from .routers.resource_router import router as resource_router
from .static_mounts import configure_static_mounts
from .telemetry.jaeger_provider import setup_jaeger
from .version.models import VersionInfo
from .version.router import router as version_router


def create_app() -> FastAPI:
    if not inject.is_configured():
        inject.configure(
            lambda binder: configure_bindings(binder=binder, config_file="app.conf"),
        )

    version_info: VersionInfo = inject.instance(VersionInfo)

    app = FastAPI(
        title=APP_NAME,
        version=version_info.version,
        docs_url=None,
        redoc_url=None,
    )

    app_config: AppConfig = inject.instance(AppConfig)

    configure_static_mounts(app, app_config)
    register_exception_handlers(app)
    setup_jaeger(app)

    for router in [
        health_router,
        dicom_router,
        binary_router,
        resource_router,
        version_router,
        docs_router,
    ]:
        app.include_router(router)

    if app_config.oauth.mock_oauth_servers:
        app.include_router(auth_mock_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_headers=["*"],
    )

    return app
