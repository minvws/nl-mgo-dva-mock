import datetime
import json
from os import path
from typing import Any, List, Optional
from urllib.parse import unquote

from fastapi import Request
from pydantic import BaseModel


class HCIMResourceMatch(BaseModel):
    required_params: Optional[List[str]]
    resource_path: str
    fhir_version: str

    def match(self, params: List[str]) -> bool:
        if not self.required_params:
            return True

        # replace dynamic placeholders
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        required_params = [
            param.replace("{{TODAY}}", today_date)
            for param in self.required_params or []
        ]

        return all(param in params for param in required_params)


class HCIMResource(BaseModel):
    data_service: str
    matches: List[HCIMResourceMatch]


class HCIMResourceMatcher:
    def __init__(
        self,
        endpoints: dict[str, HCIMResource] | None = None,
        hcim_dir: str | None = None,
        endpoints_filename: str = "endpoints.json",
    ) -> None:
        self.hcim_dir = hcim_dir
        self.endpoints_filename = endpoints_filename
        self.endpoints: dict[str, HCIMResource] = (
            endpoints if endpoints is not None else self.__load_endpoints()
        )

    def __load_endpoints(self) -> dict[str, HCIMResource]:
        if self.hcim_dir is None:
            raise ValueError("hcim_dir is required if endpoints is not provided")

        with open(path.join(self.hcim_dir, self.endpoints_filename), "r") as file:
            endpoints: dict[str, Any] = json.loads(file.read())
            return {uri: (HCIMResource(**config)) for uri, config in endpoints.items()}

    def match_resource(self, request: Request) -> HCIMResourceMatch | None:
        request_params = [
            unquote(param) for param in str(request.query_params).split("&")
        ]

        hcim_resource = self.endpoints.get(request.url.path, None)
        if hcim_resource is None:
            return None

        return next(
            (
                hcim_resource_match
                for hcim_resource_match in hcim_resource.matches
                if hcim_resource_match.match(request_params)
            ),
            None,
        )
