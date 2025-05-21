import os
from pathlib import Path

import pytest

from fhir.models import Resource
from fhir.scanner import ResourceScanner


@pytest.fixture
def mock_resource_path(tmp_path: Path) -> str:
    tmp_resource_path = tmp_path / "resources"
    tmp_resource_path.mkdir()

    return str(tmp_resource_path)


@pytest.fixture
def resource_scanner(mock_resource_path: str) -> ResourceScanner:
    return ResourceScanner(mock_resource_path)


@pytest.fixture
def store_resource_files(mock_resource_path: str) -> None:
    resource_files = {
        "Patient": [
            "Index.json",
            "nl-core-patient-03.json",
            "nl-core-patient-02.json",
            "nl-core-patient-01.json",
        ],
        "Encounter": [
            "nl-core-encounter-01.json",
        ],
        "Empty": {},
    }

    for resource, stubs in resource_files.items():
        os.makedirs(os.path.join(mock_resource_path, resource))

        for stub in stubs:
            with open(os.path.join(mock_resource_path, resource, stub), "w") as f:
                f.write("{}")


@pytest.mark.usefixtures("store_resource_files")
def test_scan(resource_scanner: ResourceScanner) -> None:
    resources = resource_scanner.scan()

    assert len(resources) == 2
    assert isinstance(resources[0], Resource)

    assert resources[0].name == "Encounter"
    assert resources[0].endpoints == [
        "/fhir/Encounter/nl-core-encounter-01",
    ]
    assert isinstance(resources[1], Resource)

    assert resources[1].name == "Patient"
    assert resources[1].endpoints == [
        "/fhir/Patient",
        "/fhir/Patient/nl-core-patient-01",
        "/fhir/Patient/nl-core-patient-02",
        "/fhir/Patient/nl-core-patient-03",
    ]
