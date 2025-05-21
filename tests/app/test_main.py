import os

import inject
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pytest_mock import MockerFixture

from app.authentication.routers import router as auth_mock_router
from app.config.models import AppConfig, OAuthConfig
from app.config.services import ConfigParser
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
