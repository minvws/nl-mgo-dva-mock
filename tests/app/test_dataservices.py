import builtins
import json
import os
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from inject import Binder
from pytest_mock import MockerFixture

from app.binary.services import BinaryRouteResolver
from app.config.models import AppConfig
from tests.utils import (
    clear_bindings,
    configure_bindings,
    load_app_config,
)

json_file_path = os.path.join(
    os.path.dirname(__file__), "../../app", "hcim", "endpoints.json"
)
with open(json_file_path, "r") as file:
    endpoints_data = json.load(file)

endpoints = []
for endpoint, data in endpoints_data.items():
    for match in data["matches"]:
        required_params = match.get("required_params", [])
        params_dict: Dict[Any, Any] = {}
        fhir_version = match.get("fhir_version")
        for param in required_params:
            key, value = param.split("=")
            if key in params_dict:
                if isinstance(params_dict[key], list):
                    params_dict[key].append(value)
                else:
                    params_dict[key] = [params_dict[key], value]
            else:
                params_dict[key] = value

        params_dict = {
            key: value.replace("{{TODAY}}", time.strftime("%Y-%m-%d"))
            if "{{TODAY}}" in value
            else value
            for key, value in params_dict.items()
        }

        endpoints.append((endpoint, params_dict, fhir_version))


@pytest.mark.parametrize("endpoint,params,fhir_version", endpoints)
def test_url_status_code_200(
    endpoint: Any,
    params: Any,
    fhir_version: Any,
    test_client: TestClient,
    mocker: MockerFixture,
    medmij_request_id: str,
) -> None:
    """This test Loops through all the endpoints in the endpoints.json file and checks if they return status code 200"""
    response = test_client.get(
        endpoint,
        params=params,
        headers={
            "Accept": "application/fhir+json; fhirVersion=" + fhir_version,
            "MedMij-Request-ID": medmij_request_id,
        },
    )
    response.request.url

    assert response.status_code == 200


@pytest.mark.parametrize("endpoint,params, fhir_version", endpoints)
def test_demo_mode_gets_resources_from_demo_path(
    endpoint: Any,
    params: Any,
    fhir_version: str,
    test_client: TestClient,
    mocker: MockerFixture,
    medmij_request_id: str,
) -> None:
    """This test Loops through all the endpoints in the endpoints.json file and checks if they return status code 200"""

    def bindings_override(binder: Binder) -> Binder:
        config = load_app_config()
        config.use_demo_hcims = True
        binary_route_resolver = BinaryRouteResolver(use_demo_hcims=True)

        binder.bind(AppConfig, config)
        binder.bind(BinaryRouteResolver, binary_route_resolver)
        return binder

    configure_bindings(bindings_override=bindings_override)

    open_spy = mocker.patch("builtins.open", wraps=builtins.open)

    response = test_client.get(
        endpoint,
        params=params,
        headers={
            "Accept": "application/fhir+json; fhirVersion=" + fhir_version,
            "MedMij-Request-ID": medmij_request_id,
        },
    )
    full_url = response.request.url

    assert response.status_code == 200

    open_spy_args = open_spy.call_args
    assert "/demo/" in open_spy_args[0][0], f"URL: {full_url} did not use demo data"

    clear_bindings()


def test_vaccination_immunization_v2_endpoint_returns_expected_bundle(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/66/fhir/Immunization",
        params=[
            ("_include", "Immunization:patient"),
            ("_include", "Immunization:location"),
            ("_include", "Immunization:performer"),
        ],
        headers={
            "Accept": "application/fhir+json; fhirVersion=4.0",
            "MedMij-Request-ID": medmij_request_id,
        },
    )

    assert response.status_code == 200

    json = response.json()
    assert json["resourceType"] == "Bundle"
    assert json["link"][0]["url"] == (
        "https://mock/66/fhir/Immunization"
        "?_include=Immunization%3Apatient"
        "&_include=Immunization%3Alocation"
        "&_include=Immunization%3Aperformer"
    )
    assert json["entry"][0]["resource"]["meta"]["profile"] == [
        "http://nictiz.nl/fhir/StructureDefinition/imm-Vaccination-event"
    ]


def test_vaccination_immunization_v2_endpoint_requires_include_parameters(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/66/fhir/Immunization",
        headers={
            "Accept": "application/fhir+json; fhirVersion=4.0",
            "MedMij-Request-ID": medmij_request_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["issue"][0]["code"] == "not-found"


def test_vaccination_immunization_v1_endpoint_is_removed(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/63/fhir/Immunization",
        headers={
            "Accept": "application/fhir+json; fhirVersion=4.0",
            "MedMij-Request-ID": medmij_request_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["issue"][0]["code"] == "not-found"
