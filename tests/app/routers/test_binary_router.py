from fastapi.testclient import TestClient


def test_binary_endpoint_can_return_raw_pdf(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/51/fhir/Binary/pdfa-binary1",
        headers={
            "Accept": "application/pdf",
            "MedMij-Request-ID": medmij_request_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_binary_endpoint_rejects_unsupported_representation(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/51/fhir/Binary/pdfa-binary1",
        headers={
            "Accept": "image/jpeg",
            "MedMij-Request-ID": medmij_request_id,
        },
    )

    assert response.status_code == 406
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-supported",
                "diagnostics": (
                    "The requested representation is not supported. "
                    "Supported values: 'application/fhir+json; "
                    "fhirVersion=3.0', 'application/pdf'"
                ),
            }
        ],
    }


def test_binary_endpoint_returns_422_without_medmij_request_id(
    test_client: TestClient,
) -> None:
    response = test_client.get(
        "/51/fhir/Binary/pdfa-binary1",
        headers={"Accept": "application/pdf"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["header", "MedMij-Request-ID"]
