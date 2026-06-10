import os

import inject
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from starlette.routing import Mount

from app.authentication.routers import router as auth_mock_router
from app.config.models import AppConfig, ImageAvailabilityConfig, OAuthConfig
from app.config.services import ConfigParser
from app.dicom.exceptions import (
    DicomError,
    DicomNotFoundError,
    DicomRenderingError,
    DicomRepresentationNotSupportedError,
)
from app.main import create_app
from app.utils import root_path
from tests.utils import clear_bindings, configure_bindings, load_app_config


def teardown_function() -> None:
    clear_bindings()


def test_create_app_parses_app_config(mocker: MockerFixture) -> None:
    config_path = root_path("app.conf")
    if not os.path.isfile(config_path):
        pytest.fail(f"This test requires config file {config_path} to exist")

    inject_configure_spy = mocker.spy(inject, "configure")
    config_parser_init_spy = mocker.spy(ConfigParser, "__init__")
    create_app()
    inject_configure_spy.assert_called()
    config_parser_init_spy.assert_called_once_with(
        mocker.ANY,
        mocker.ANY,
        root_path("app.conf"),
    )


def test_create_app_does_not_reconfigure_inject(mocker: MockerFixture) -> None:
    configure_bindings()
    inject_configure_spy = mocker.spy(inject, "configure")
    create_app()
    inject_configure_spy.assert_not_called()


def test_mock_oauth_servers_false(mocker: MockerFixture) -> None:
    app_config: AppConfig = load_app_config()
    app_config.oauth = mocker.Mock(spec=OAuthConfig)
    app_config.oauth.mock_oauth_servers = False

    configure_bindings(
        bindings_override=lambda binder: binder.bind(AppConfig, app_config)
    )

    app: FastAPI = create_app()

    auth_mock_router_paths = [
        route.path for route in auth_mock_router.routes if isinstance(route, APIRoute)
    ]
    app_routes_paths = [
        route.path for route in app.routes if isinstance(route, APIRoute)
    ]

    assert all(path not in app_routes_paths for path in auth_mock_router_paths)


def test_mock_oauth_servers_imports_mock_routes(mocker: MockerFixture) -> None:
    app_config: AppConfig = load_app_config()
    app_config.oauth = mocker.Mock(spec=OAuthConfig)
    app_config.oauth.mock_oauth_servers = True

    configure_bindings(
        bindings_override=lambda binder: binder.bind(AppConfig, app_config)
    )

    app: FastAPI = create_app()

    auth_mock_router_paths = [
        route.path for route in auth_mock_router.routes if isinstance(route, APIRoute)
    ]
    app_routes_paths = [
        route.path for route in app.routes if isinstance(route, APIRoute)
    ]

    assert all(path in app_routes_paths for path in auth_mock_router_paths)


def test_serve_client_app_false_does_not_mount_client(
    mocker: MockerFixture,
) -> None:
    app_config: AppConfig = load_app_config()
    app_config.image_availability = mocker.Mock(spec=ImageAvailabilityConfig)
    app_config.image_availability.serve_client_app = False

    configure_bindings(
        bindings_override=lambda binder: binder.bind(AppConfig, app_config)
    )

    app: FastAPI = create_app()

    app_mount_paths = [route.path for route in app.routes if isinstance(route, Mount)]

    assert "/client" not in app_mount_paths


def test_serve_client_app_true_mounts_client(mocker: MockerFixture) -> None:
    app_config: AppConfig = load_app_config()
    app_config.image_availability = mocker.Mock(spec=ImageAvailabilityConfig)
    app_config.image_availability.serve_client_app = True

    configure_bindings(
        bindings_override=lambda binder: binder.bind(AppConfig, app_config)
    )

    app: FastAPI = create_app()

    app_mount_paths = [route.path for route in app.routes if isinstance(route, Mount)]

    assert "/client" in app_mount_paths


def test_docs_route_returns_swagger_ui() -> None:
    configure_bindings()

    client = TestClient(create_app())
    response = client.get("/docs")

    assert response.status_code == 200
    assert "/openapi.json" in response.text
    assert "/static/swagger-ui-bundle.js" in response.text
    assert "/static/swagger-ui.css" in response.text


def test_swagger_oauth_redirect_route_exists() -> None:
    configure_bindings()

    client = TestClient(create_app())
    response = client.get("/docs/oauth2-redirect")

    assert response.status_code == 200


def test_openapi_rendered_routes_expose_correct_frame_parameter() -> None:
    configure_bindings()

    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]
    rendered_endpoint_parameters = paths[
        "/9000002/wado/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered"
    ]["get"]["parameters"]
    rendered_endpoint_parameter_names = {
        parameter["name"] for parameter in rendered_endpoint_parameters
    }

    assert "frame_id" not in rendered_endpoint_parameter_names

    frame_rendered_endpoint_parameters = paths[
        "/9000002/wado/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_id}/rendered"
    ]["get"]["parameters"]
    frame_rendered_endpoint_parameter_names = {
        parameter["name"] for parameter in frame_rendered_endpoint_parameters
    }

    assert "frame_id" in frame_rendered_endpoint_parameter_names


def test_global_handler_maps_dicom_not_found() -> None:
    configure_bindings()
    app = create_app()

    @app.get("/__test__/dicom-not-found")
    def raise_dicom_not_found() -> None:
        raise DicomNotFoundError("not found")

    response = TestClient(app).get("/__test__/dicom-not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}


def test_global_handler_maps_dicom_representation_not_supported() -> None:
    configure_bindings()
    app = create_app()

    @app.get("/__test__/dicom-not-acceptable")
    def raise_dicom_not_acceptable() -> None:
        raise DicomRepresentationNotSupportedError({"application/dicom"})

    response = TestClient(app).get("/__test__/dicom-not-acceptable")

    assert response.status_code == 406
    assert "not supported" in response.json()["detail"]


def test_global_handler_maps_generic_dicom_error() -> None:
    configure_bindings()
    app = create_app()

    @app.get("/__test__/dicom-generic")
    def raise_generic_dicom_error() -> None:
        raise DicomError("internal detail should stay hidden")

    response = TestClient(app).get("/__test__/dicom-generic")

    assert response.status_code == 500
    assert response.json() == {"detail": "Unexpected DICOM server error"}


def test_global_handler_maps_dicom_rendering_error() -> None:
    configure_bindings()
    app = create_app()

    @app.get("/__test__/dicom-rendering")
    def raise_dicom_rendering_error() -> None:
        raise DicomRenderingError("rendering failed")

    response = TestClient(app).get("/__test__/dicom-rendering")

    assert response.status_code == 500
    assert response.json() == {"detail": "rendering failed"}
