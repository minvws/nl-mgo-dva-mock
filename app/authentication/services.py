import uuid
import inject

from fastapi import Depends

from .exceptions import AuthorizationHttpException


class AuthenticationMock:
    def authenticate(self, scope: str) -> str:
        # Mock authentication logic
        if scope != "eenofanderezorgaanbieder":
            raise AuthorizationHttpException(
                status_code=401, detail={"error": "Mocked Authentication failure"}
            )

        return str(object=uuid.uuid4())


class UrlBuilder:
    def __init__(self) -> None:
        self._params: dict[str, str] = {}

    def add_param(self, name: str, value: str) -> None:
        self._params[name] = value

    def __reset(self) -> None:
        self._params = {}

    def build(self, location: str) -> str:
        if "?" in location:
            location += "&"
        else:
            location += "?"

        location += "&".join([f"{k}={v}" for k, v in self._params.items()])

        self.__reset()

        return location


class MedMijAuthCallbackUrlDirector:
    @inject.autoparams()
    def __init__(self, builder: UrlBuilder) -> None:
        self._builder: UrlBuilder = builder

    def build_callback_url(self, callback_uri: str, state: str, code: str) -> str:
        self._builder.add_param(name="state", value=state)
        self._builder.add_param(name="code", value=code)

        return self._builder.build(location=callback_uri)
