import pytest
from pydantic import ValidationError

from app.authentication.schemas import AuthorizationCodeRequest, RefreshTokenRequest


@pytest.mark.parametrize(
    "missing_param",
    [
        "grant_type",
        "code",
        "redirect_uri",
        "client_id",
    ],
)
def test_it_validates_authorization_code_request(missing_param: str) -> None:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": "abc-123",
        "redirect_uri": "http://example.com/callback",
        "client_id": "random-client-id",
    }

    data.pop(missing_param)

    with pytest.raises(ValidationError) as e:
        # Type ignored because false positive
        AuthorizationCodeRequest(**data)  # type: ignore

    assert len(e.value.errors()) == 1
    assert e.value.errors()[0]["loc"][0] == missing_param


@pytest.mark.parametrize(
    "missing_param",
    [
        "grant_type",
        "refresh_token",
        "client_id",
    ],
)
def test_it_validates_refresh_token_requests(missing_param: str) -> None:
    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": "abc-123",
        "client_id": "random-client-id",
    }

    data.pop(missing_param)

    with pytest.raises(ValidationError) as e:
        # Type ignored because false positive
        RefreshTokenRequest(**data)  # type: ignore

    assert len(e.value.errors()) == 1
    assert e.value.errors()[0]["loc"][0] == missing_param
