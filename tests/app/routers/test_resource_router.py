import json
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.config.models import AppConfig, LoggingConfig, OAuthConfig, TelemetryConfig
from app.hcim.matchers import HCIMResourceMatch, HCIMResourceMatcher
from app.routers.resource_router import __handle_request
from fhir.models import Resource


@pytest.mark.parametrize(
    "endpoint",
    ["/99/fhir/Patient/nl-core-patient-01", "/99/fhir/Patient/nl-core-patient-01/"],
)
def test_show(
    endpoint: str,
    test_client: TestClient,
) -> None:
    response = test_client.get(
        url=endpoint,
        headers={"Accept": "application/fhir+json; fhirVersion=3.0"},
    )

    assert response.status_code == 200
    assert response.json().get("id") == "nl-core-patient-01"
    assert response.json().get("resourceType") == "Patient"


def test_not_found(
    test_client: TestClient,
) -> None:
    response = test_client.get(
        url="/99/fhir/NonExistentResource/123",
        headers={"Accept": "application/fhir+json; fhirVersion=3.0"},
    )
    assert response.status_code == 404
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-found",
                "diagnostics": "The resource http://testserver/99/fhir/NonExistentResource/123 is not supported by the mock server",
            },
        ],
    }


def test_list_resources(
    test_client: TestClient,
) -> None:
    response = test_client.get("/fhir/resources")

    assert response.status_code == 200

    json = response.json()
    assert isinstance(json, list)

    assert len(json) > 0

    for item in json:
        assert Resource(**item)


def test_handle_request_with_valid_hcim_response(mocker: MockerFixture) -> None:
    resource_path = "/valid/path/to/resource"

    hcim_service = mocker.patch.object(HCIMResourceMatcher, "match_resource")
    hcim_service.match_resource.return_value = HCIMResourceMatch(
        required_params=None, resource_path=resource_path, fhir_version="3.0"
    )

    mock_open = mocker.patch("builtins.open")
    mock_file = mock_open.return_value.__enter__.return_value
    mock_file.read.return_value = json.dumps({"id": "123", "resourceType": "Patient"})

    request = mocker.MagicMock(spec=Request)
    request.headers = mocker.Mock()
    request.headers.get.return_value = "application/fhir+json; fhirVersion=3.0"

    response = __handle_request(
        AppConfig(
            base_url="http://localhost",
            logging=LoggingConfig(),
            oauth=OAuthConfig(),
            telemetry=TelemetryConfig(
                service_name="mock",
                collector_grpc_url="",
                enabled=False,
            ),
        ),
        hcim_service,
        "Patient",
        "123",
        request,
        accept_header="application/fhir+json; fhirVersion=3.0",
    )

    mock_open.assert_called_once_with(resource_path)
    assert json.loads(response.body) == {"id": "123", "resourceType": "Patient"}
    assert response.status_code == 200


def test_handle_request_hcim_response_none_but_id_returns_response(
    mocker: MockerFixture,
) -> None:
    hcim_service = mocker.patch.object(HCIMResourceMatcher, "match_resource")
    hcim_service.match_resource.return_value = None

    mock_json = mocker.mock_open(read_data='{"id": "123", "resourceType": "Patient"}')
    mocker.patch("builtins.open", mock_json)

    request = mocker.MagicMock(spec=Request)
    request.headers = mocker.Mock()
    request.headers.get.return_value = "application/fhir+json; fhirVersion=3.0"

    response = __handle_request(
        AppConfig(
            base_url="http://localhost",
            logging=LoggingConfig(),
            oauth=OAuthConfig(),
            telemetry=TelemetryConfig(
                service_name="mock",
                collector_grpc_url="",
                enabled=False,
            ),
        ),
        hcim_service,
        "Patient",
        "123",
        request,
        accept_header="application/fhir+json; fhirVersion=3.0",
    )

    assert json.loads(response.body) == {"id": "123", "resourceType": "Patient"}
    assert response.status_code == 200


def test_handle_request_hcim_response_non_existing_path_returns_404(
    mocker: MockerFixture,
) -> None:
    mock_match = mocker.Mock(spec=HCIMResourceMatch)
    mock_match.resource_path = "/non/existing/path"
    mock_match.fhir_version = "3.0"
    hcim_service = mocker.patch.object(HCIMResourceMatcher, "match_resource")
    hcim_service.match_resource.return_value = mock_match

    request = mocker.MagicMock(spec=Request)
    request.headers = mocker.Mock()
    request.headers.get.return_value = "application/fhir+json; fhirVersion=3.0"

    response = __handle_request(
        AppConfig(
            base_url="http://localhost",
            logging=LoggingConfig(),
            oauth=OAuthConfig(),
            telemetry=TelemetryConfig(
                service_name="mock",
                collector_grpc_url="",
                enabled=False,
            ),
        ),
        hcim_service,
        "Patient",
        "123",
        request,
        accept_header="application/fhir+json; fhirVersion=3.0",
    )

    assert response.status_code == 404


def test_no_id_no_hcim_match_returns_404(test_client: TestClient) -> None:
    response = test_client.get(
        url="/99/fhir/Patient",
        headers={"Accept": "application/fhir+json; fhirVersion=3.0"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-found",
                "diagnostics": "The resource http://testserver/99/fhir/Patient is not supported by the mock server",
            },
        ],
    }


@pytest.mark.parametrize(
    "resource_file",
    [
        str(resource_file)
        for resource_file in Path("fhir/resources").rglob("*.json")
        if not any(
            exclude_path in str(resource_file)
            for exclude_path in [
                "demo",
                "BGZ",
                "GPData",
                "PDFA",
                "Vaccination-Immunization",
            ]
        )
    ],
)
def test_it_can_request_singular_resources(
    test_client: TestClient, resource_file: str
) -> None:
    str_path = resource_file.replace("fhir/resources/", "").replace(".json", "")
    response = test_client.get(
        url=f"/99/fhir/{str_path}",
        headers={"Accept": "application/fhir+json; fhirVersion=3.0"},
    )

    assert response.status_code == 200


def test_invalid_format_header(test_client: TestClient) -> None:
    response = test_client.get(
        "/48/fhir/NutritionOrder",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-supported",
                "diagnostics": f"The 'Accept' header value: 'application/json' is not supported. Supported value: 'application/fhir+json; fhirVersion=3.0'",
            }
        ],
    }


def test_missing_format_header(test_client: TestClient) -> None:
    response = test_client.get(
        "/48/fhir/NutritionOrder",
    )

    assert response.status_code == 400
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-supported",
                "diagnostics": f"The 'Accept' header value: '*/*' is not supported. Supported value: 'application/fhir+json; fhirVersion=3.0'",
            }
        ],
    }


def test_www_authenticate_header_is_sent_on_error(test_client: TestClient) -> None:
    response = test_client.get(
        "/48/fhir/NutritionOrder",
    )

    assert response.status_code == 400
    assert (
        response.headers.get("WWW-Authenticate")
        == 'Bearer error="invalid_request", error_description="Requested FHIR version not supported"'
    )


@pytest.mark.parametrize(
    "medmij_request_id",
    [None, "123"],
)
def test_medmij_request_id_header_is_passed_on_if_exists(
    test_client: TestClient, medmij_request_id: str | None
) -> None:
    headers = {"Accept": "application/fhir+json; fhirVersion=3.0"}
    if medmij_request_id:
        headers["MedMij-Request-ID"] = medmij_request_id

    response = test_client.get(
        "/48/fhir/NutritionOrder",
        headers=headers,
    )

    assert response.status_code == 200
    if medmij_request_id:
        assert response.headers.get("MedMij-Request-ID") == medmij_request_id
    else:
        assert response.headers.get("MedMij-Request-ID") is None
