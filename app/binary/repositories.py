import json
from abc import ABC, abstractmethod

from app.binary.exceptions import (
    BinaryResourceNotFoundError,
    InvalidBinaryPayloadError,
)
from app.binary.schemas import BinaryResource


class BinaryRepository(ABC):
    @abstractmethod
    def load(self, resource_path: str) -> BinaryResource: ...


class BinaryFileRepository(BinaryRepository):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def load(self, resource_path: str) -> BinaryResource:
        try:
            with open(resource_path) as file:
                raw_content = file.read().replace("{{BASE_URL}}", self.base_url)
        except FileNotFoundError as exc:
            raise BinaryResourceNotFoundError(resource_path) from exc

        parsed = json.loads(raw_content)
        content_type = parsed.get("contentType")

        """ Data is used from FHIR version 4.0.1, content is used in older versions.(STU3). Since both PDFA and ImageAvailability are served from this repo, we need to support both fields. """
        payload = parsed.get("data") or parsed.get("content")

        if not isinstance(payload, str):
            raise InvalidBinaryPayloadError(
                "Binary payload must be a base64 string in 'data' (R4) or 'content' (STU3)."
            )

        return BinaryResource(
            raw_content=raw_content,
            content_type=content_type,
            payload_base64=payload,
        )
