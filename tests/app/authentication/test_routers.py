import json
import uuid
from urllib.parse import unquote

from fastapi.testclient import TestClient
from httpx import Response
from pytest_mock import MockerFixture

from app.authentication.exceptions import (
    AuthorizationHttpException,
)
from app.authentication.services import (
    AuthenticationMock,
    MedMijAuthCallbackUrlDirector,
)
from app.config.models import AppConfig, OAuthConfig
from app.main import create_app
from tests.utils import clear_bindings, configure_bindings


def test_authenticate_success(mocker: MockerFixture, test_client: TestClient) -> None:
    mock_builder: MedMijAuthCallbackUrlDirector = mocker.Mock(
        MedMijAuthCallbackUrlDirector
    )
    mock_builder_build_callback_url = mocker.patch.object(
        mock_builder, "build_callback_url"
    )
    mock_builder_build_callback_url.return_value = (
        "http://example.com/auth/callback?state=xyz&code=test_code"
    )

    configure_bindings(
        bindings_override=lambda binder: binder.bind(
            MedMijAuthCallbackUrlDirector, mock_builder
        )
    )

    response: Response = test_client.get(
        "/auth",
        params={
            "redirect_uri": "http://example.com/auth/callback",
            "scope": "eenofanderezorgaanbieder",
            "state": "xyz",
            "X-Correlation-ID": "test_correlation_id",
            "MedMij-Request-ID": "test_medmij_id",
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["Location"]
        == "http://example.com/auth/callback?state=xyz&code=test_code"
    )
    clear_bindings()


def test_authenticate_failed_authentication(
    mocker: MockerFixture, test_client: TestClient
) -> None:
    mock_authenticator = mocker.Mock(AuthenticationMock)
    mock_authenticator.authenticate.side_effect = AuthorizationHttpException(
        status_code=401
    )

    configure_bindings(
        bindings_override=lambda binder: binder.bind(
            AuthenticationMock, mock_authenticator
        )
    )

    response: Response = test_client.get(
        "/auth",
        params={
            "redirect_uri": "http://example.com/auth/callback",
            "scope": "eenofanderezorgaanbieder",
            "state": "xyz",
            "X-Correlation-ID": "test_correlation_id",
            "MedMij-Request-ID": "test_medmij_id",
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        unquote(response.headers["Location"])
        == "http://example.com/auth/callback?error=401&error_description=Authentication failed.&state=xyz"
    )
    clear_bindings()


def test_authenticate_missing_correlation_id(
    mocker: MockerFixture, test_client: TestClient
) -> None:
    response: Response = test_client.get(
        "/auth",
        params={
            "redirect_uri": "http://example.com/callback",
            "scope": "eenofanderezorgaanbieder",
            "state": "xyz",
            "MedMij-Request-ID": "test_medmij_id",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    json_response = response.json()
    assert json_response["detail"][0]["loc"] == ["query", "X-Correlation-ID"]
    assert json_response["detail"][0]["msg"] == "Field required"
    clear_bindings()


def test_it_can_hand_out_access_tokens_for_authorization_code(
    test_client: TestClient, mocker: MockerFixture
) -> None:
    authorization_code = "abc-123"
    expected_acces_token = uuid.uuid4().hex
    expected_refresh_token = uuid.uuid4().hex

    mocker.patch("app.authentication.routers.uuid.uuid4").side_effect = [
        expected_acces_token,
        expected_refresh_token,
    ]

    response: Response = test_client.post(
        "/token",
        json={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": "random-client-id",
            "redirect_uri": "http://example.com/callback",
        },
        headers={
            "X-Correlation-ID": "test_correlation_id",
            "MedMij-Request-ID": "test_medmij_id",
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["access_token"] == expected_acces_token
    assert response_data["refresh_token"] == expected_refresh_token


def test_it_can_hand_out_access_tokens_for_refresh_token_request(
    test_client: TestClient, mocker: MockerFixture
) -> None:
    refresh_token = "abc-123"
    expected_acces_token = uuid.uuid4().hex
    expected_refresh_token = uuid.uuid4().hex

    mocker.patch("app.authentication.routers.uuid.uuid4").side_effect = [
        expected_acces_token,
        expected_refresh_token,
    ]

    response: Response = test_client.post(
        "/token",
        json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": "random-client-id",
        },
        headers={
            "X-Correlation-ID": "test_correlation_id",
            "MedMij-Request-ID": "test_medmij_id",
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["access_token"] == expected_acces_token
    assert response_data["refresh_token"] == expected_refresh_token


def test_it_returns_a_404_on_token_endpoint_when_mock_oauth_false(
    mocker: MockerFixture,
) -> None:
    config = mocker.Mock(spec=AppConfig)
    config.oauth = mocker.Mock(OAuthConfig)
    config.oauth.mock_oauth_servers = False

    configure_bindings(bindings_override=lambda binder: binder.bind(AppConfig, config))
    # Need to instantiate app after bindings are configured because router registration is based on bound config
    test_client = TestClient(create_app())

    response: Response = test_client.post(
        "/token",
        json={
            "grant_type": "authorization_code",
            "code": "abc-123",
            "redirect_uri": "http://example.com/callback",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    clear_bindings()


def test_it_returns_422_when_missing_correlation_id_header(
    test_client: TestClient,
) -> None:
    response: Response = test_client.post(
        "/token",
        json={
            "grant_type": "refresh_token",
            "refresh_token": "abc-123",
            "client_id": "random-client-id",
        },
        headers={
            "MedMij-Request-ID": "test_medmij_id",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "missing",
                "loc": ["header", "X-Correlation-ID"],
                "msg": "Field required",
                "input": None,
            }
        ]
    }


def test_it_returns_422_when_missing_medmij_request_id_header(
    test_client: TestClient,
) -> None:
    response: Response = test_client.post(
        "/token",
        json={
            "grant_type": "refresh_token",
            "refresh_token": "abc-123",
            "client_id": "random-client-id",
        },
        headers={
            "X-Correlation-ID": "test_correlation_id",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "missing",
                "loc": ["header", "MedMij-Request-ID"],
                "msg": "Field required",
                "input": None,
            }
        ]
    }
