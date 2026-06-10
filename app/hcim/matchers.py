import datetime
import json
import re
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


class FhirVersionAcceptHeaderMatcher:
    def fhir_version_matches(
        self, header_from_request: str | None, expected_version: str
    ) -> bool:
        """
        Check if the FHIR version in the request header matches what we expect.

        According to the FHIR spec, we support the following MIME types:
        - Primary format (FHIR STU3 onwards): 'application/fhir+json; fhirVersion=X.X'
        - Legacy format (DSTU2 to STU3): 'application/json+fhir; fhirVersion=X.X'

        Args:
            header_from_request: The Accept header from the request
            expected_version: The version we're checking against

        Returns:
            True if versions match, False otherwise
        """
        accepted_mime_types = [
            "application/fhir+json",  # Current official MIME type (STU3+)
            "application/json+fhir",  # Legacy MIME type (DSTU2-STU3)
        ]

        if header_from_request is None:
            return False

        if not any(
            header_from_request.startswith(mime_type)
            for mime_type in accepted_mime_types
        ):
            return False

        pattern = re.compile(r"fhirVersion=(\d+\.\d+(?:\.\d+)?)")
        match = pattern.search(header_from_request)

        if not match:
            return False

        return match.group(1) == expected_version
