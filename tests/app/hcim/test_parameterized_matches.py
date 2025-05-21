import time

from fastapi.testclient import TestClient


def test_it_matches_with_parameterized_urls_when_it_should(
    test_client: TestClient,
) -> None:
    date_today = time.strftime("%Y-%m-%d")

    url = (
        "/49/fhir/MedicationRequest?periodofuse=ge"
        + date_today
        + "&category=http://snomed.info/sct|16076005&_include=MedicationRequest:medication"
    )

    response = test_client.get(
        url, headers={"Accept": "application/fhir+json; fhirVersion=3.0"}
    )

    assert response.status_code == 200


def test_it_does_not_match_with_parameterized_urls_when_it_should_not(
    test_client: TestClient,
) -> None:
    url = "/49/fhir/MedicationRequest?periodofuse=ge2020-01-01&category=http://snomed.info/sct|16076005&_include=MedicationRequest:medication"

    response = test_client.get(url)

    assert response.status_code == 404
