from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config.models import AppConfig
from .utils import root_path


def configure_static_mounts(app: FastAPI, app_config: AppConfig) -> None:
    app.mount("/static", StaticFiles(directory=root_path("static")), name="static")

    if app_config.image_availability.serve_client_app:
        app.mount(
            "/client",
            StaticFiles(directory=root_path("static", "bbs-client"), html=True),
            name="bbs-client",
        )
