from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel


class GrantType(str, Enum):
    refresh_token = "refresh_token"
    authorization_code = "authorization_code"


class TokenRequest(BaseModel):
    grant_type: GrantType
    client_id: str


class AuthorizationCodeRequest(TokenRequest):
    grant_type: Literal[GrantType.authorization_code]
    code: str
    redirect_uri: str


class RefreshTokenRequest(TokenRequest):
    grant_type: Literal[GrantType.refresh_token]
    refresh_token: str


TokenRequestModel = Union[AuthorizationCodeRequest, RefreshTokenRequest]
