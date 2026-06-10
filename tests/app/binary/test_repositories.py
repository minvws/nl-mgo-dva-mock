import json
from pathlib import Path

import pytest

from app.binary.exceptions import (
    BinaryResourceNotFoundError,
    InvalidBinaryPayloadError,
)
from app.binary.repositories import BinaryFileRepository


def write_binary_resource(tmp_path: Path, payload: dict[str, object]) -> str:
    resource_path = tmp_path / "binary.json"
    resource_path.write_text(json.dumps(payload))
    return str(resource_path)


@pytest.mark.parametrize(
    ("payload", "expected_content_type", "expected_payload"),
    [
        (
            {"contentType": "application/pdf", "data": "pdf-data"},
            "application/pdf",
            "pdf-data",
        ),
        (
            {"contentType": "application/pdf", "content": "pdf-data"},
            "application/pdf",
            "pdf-data",
        ),
        ({"data": "pdf-data"}, None, "pdf-data"),
        ({"contentType": None, "data": "pdf-data"}, None, "pdf-data"),
    ],
)
def test_load_maps_binary_resource_fields(
    tmp_path: Path,
    payload: dict[str, object],
    expected_content_type: str | None,
    expected_payload: str | None,
) -> None:
    resource_path = write_binary_resource(tmp_path, payload)
    repository = BinaryFileRepository(base_url="http://localhost")
    result = repository.load(resource_path)

    assert json.loads(result.raw_content) == payload
    assert result.content_type == expected_content_type
    assert result.payload_base64 == expected_payload


@pytest.mark.parametrize(
    "payload",
    [
        {"contentType": "application/json", "data": {"key": "value"}},
        {"contentType": "application/json", "data": ["value"]},
        {"contentType": "application/json", "data": 123},
        {"contentType": "application/json", "content": {"key": "value"}},
        {"contentType": "application/json", "content": ["value"]},
        {"contentType": "application/json", "content": 123},
    ],
)
def test_load_raises_for_invalid_payload_type(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    resource_path = write_binary_resource(tmp_path, payload)
    repository = BinaryFileRepository(base_url="http://localhost")

    with pytest.raises(InvalidBinaryPayloadError):
        repository.load(resource_path)


@pytest.mark.parametrize(
    ("payload", "expected_url_values"),
    [
        (
            {
                "contentType": "application/json",
                "data": "test-data",
                "url": "{{BASE_URL}}/resource",
            },
            {"url": "http://example.com/resource"},
        ),
        (
            {
                "contentType": "application/json",
                "data": "test-data",
                "url1": "{{BASE_URL}}/resource1",
                "url2": "{{BASE_URL}}/resource2",
            },
            {
                "url1": "http://example.com/resource1",
                "url2": "http://example.com/resource2",
            },
        ),
    ],
)
def test_load_replaces_base_url_tokens(
    tmp_path: Path,
    payload: dict[str, object],
    expected_url_values: dict[str, str],
) -> None:
    resource_path = write_binary_resource(tmp_path, payload)
    repository = BinaryFileRepository(base_url="http://example.com")

    result = repository.load(resource_path)

    for key, expected_value in expected_url_values.items():
        assert json.loads(result.raw_content)[key] == expected_value


def test_load_raises_for_missing_resource() -> None:
    repository = BinaryFileRepository(base_url="http://localhost")
    with pytest.raises(BinaryResourceNotFoundError, match="/non/existent/file.json"):
        repository.load("/non/existent/file.json")
