import faker
import pytest

from app.authentication.exceptions import AuthorizationHttpException
from app.authentication.services import (
    AuthenticationMock,
    MedMijAuthCallbackUrlDirector,
)
from app.authentication.services import UrlBuilder


class TestAuthenticationMock:
    def test_authentication_failed_exception(self) -> None:
        auth_mock = AuthenticationMock()

        with pytest.raises(AuthorizationHttpException):
            auth_mock.authenticate(scope="invalid_scope")


class TestMedMijAuthCallbackUrlBuilder:
    def test_it_creates_correct_callback_url(self) -> None:
        builder = MedMijAuthCallbackUrlDirector(builder=UrlBuilder())

        callback_url: str = "https://example.com/callback"
        test_state: str = faker.Faker().word()
        code: str = "123"

        url: str = builder.build_callback_url(
            callback_uri=callback_url,
            state=test_state,
            code=code,
        )

        assert callback_url in url
        assert test_state in url
        assert code in url

    def test_it_creates_correct_callback_url_with_params(self) -> None:
        builder = MedMijAuthCallbackUrlDirector(builder=UrlBuilder())

        callback_url: str = "https://example.com/callback?param1=value1"
        test_state: str = faker.Faker().word()
        code: str = "123"

        url: str = builder.build_callback_url(
            callback_uri=callback_url,
            state=test_state,
            code=code,
        )

        assert callback_url in url
        assert test_state in url
        assert code in url
        assert "param1=value1" in url
