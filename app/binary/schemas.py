from dataclasses import dataclass
from typing import Annotated


@dataclass(frozen=True)
class BinaryResource:
    raw_content: Annotated[
        str,
        "The raw JSON content of the binary resource, with any placeholders replaced.",
    ]
    content_type: str
    payload_base64: str


@dataclass(frozen=True)
class BinaryRouteTarget:
    resource_path: str
    expected_fhir_version: str | None
