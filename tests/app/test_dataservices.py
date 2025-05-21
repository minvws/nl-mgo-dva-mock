import builtins
import json
import os
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.config.models import AppConfig
from tests.utils import clear_bindings, configure_bindings, load_app_config

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
) -> None:
    """This test Loops through all the endpoints in the endpoints.json file and checks if they return status code 200"""
    response = test_client.get(
        endpoint,
        params=params,
        headers={"Accept": "application/fhir+json; fhirVersion=" + fhir_version},
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
) -> None:
    """This test Loops through all the endpoints in the endpoints.json file and checks if they return status code 200"""

    config = load_app_config()
    config.use_demo_hcims = True
    configure_bindings(bindings_override=lambda binder: binder.bind(AppConfig, config))
    open_spy = mocker.spy(builtins, "open")

    response = test_client.get(
        endpoint,
        params=params,
        headers={"Accept": "application/fhir+json; fhirVersion=" + fhir_version},
    )
    full_url = response.request.url

    assert response.status_code == 200

    open_spy_args = open_spy.call_args
    assert "/demo/" in open_spy_args[0][0], f"URL: {full_url} did not use demo data"

    clear_bindings()
