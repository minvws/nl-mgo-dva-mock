import inject
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .authentication.routers import router as auth_mock_router
from .bindings import configure_bindings
from .config.models import AppConfig
from .constants import APP_NAME
from .routers.resource_router import router as resource_router
from .telemetry.jaeger_provider import setup_jaeger
from .utils import root_path
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

    app.mount("/static", StaticFiles(directory=root_path("static")), name="static")

    app_config: AppConfig = inject.instance(AppConfig)

    setup_jaeger(app)

    for router in [
        resource_router,
        version_router,
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
