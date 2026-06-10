from pathlib import Path

from fastapi.testclient import TestClient


def fhir_r4_headers(medmij_request_id: str) -> dict[str, str]:
    return {
        "Accept": "application/fhir+json; fhirVersion=4.0",
        "MedMij-Request-ID": medmij_request_id,
    }


def medmij_headers(medmij_request_id: str, accept: str | None = None) -> dict[str, str]:
    headers = {"MedMij-Request-ID": medmij_request_id}
    if accept is not None:
        headers["Accept"] = accept
    return headers


SINGLE_PATIENT_REFERENCE = "Patient/ia-patient"
SINGLE_PATIENT_DISPLAY = "Patient. XXX-OpdeFoto"
WADO_URL_PREFIX = "https://mock/9000002/wado/studies/"
REPRESENTATIVE_STUDY_UID = "1.2.752.24.7.3059655634.36522"


def test_documentreference_search_returns_searchset(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference",
        params={"status": "current"},
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["resourceType"] == "Bundle"
    assert payload["type"] == "searchset"
    assert payload["total"] == 13
    assert all(entry["resource"]["status"] == "current" for entry in payload["entry"])
    assert all(
        entry["resource"]["subject"]["reference"] == SINGLE_PATIENT_REFERENCE
        for entry in payload["entry"]
    )
    assert all(
        entry["resource"]["subject"]["display"] == SINGLE_PATIENT_DISPLAY
        for entry in payload["entry"]
    )


def test_documentreference_search_returns_masteridentifier_for_all_results(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference",
        params={"status": "current"},
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert all("masterIdentifier" in entry["resource"] for entry in payload["entry"])
    assert all(
        entry["resource"]["masterIdentifier"]["value"] for entry in payload["entry"]
    )


def test_documentreference_search_requires_status_current(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference",
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 404
    assert response.json()["resourceType"] == "OperationOutcome"


def test_documentreference_search_can_filter_reports(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference",
        params={"status": "current", "contenttype": "application/pdf"},
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 5
    assert all(
        entry["resource"]["category"][0]["coding"][0]["code"] == "REPORTS"
        for entry in payload["entry"]
    )
    assert all(
        entry["resource"]["content"][0]["attachment"]["contentType"]
        == "application/pdf"
        for entry in payload["entry"]
    )


def test_documentreference_search_can_filter_images(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference",
        params={"status": "current", "contenttype": "application/dicom"},
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 9
    assert all(
        entry["resource"]["category"][0]["coding"][0]["code"] == "IMAGES"
        for entry in payload["entry"]
    )
    assert all(
        entry["resource"]["content"][0]["attachment"]["contentType"]
        == "application/dicom+json"
        for entry in payload["entry"]
    )
    assert all(
        entry["resource"]["content"][0]["attachment"]["url"].startswith(WADO_URL_PREFIX)
        for entry in payload["entry"]
    )
    assert all(
        entry["resource"]["content"][0]["attachment"]["url"].endswith("/metadata")
        for entry in payload["entry"]
    )


def test_service_specific_documentreference_read_uses_r4_files(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference/ia-doc-report-01",
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resourceType"] == "DocumentReference"
    assert payload["id"] == "ia-doc-report-01"


def test_service_specific_binary_read_returns_binary(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/Binary/ia-report-01",
        headers=fhir_r4_headers(medmij_request_id),
    )

    assert response.status_code == 200
    assert response.json()["resourceType"] == "Binary"
    assert response.json()["contentType"] == "application/pdf"


def test_service_specific_binary_read_can_return_raw_pdf(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/Binary/ia-report-01",
        headers=medmij_headers(medmij_request_id, "application/pdf"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_service_specific_binary_read_rejects_unsupported_representation(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/Binary/ia-report-01",
        headers=medmij_headers(medmij_request_id, "image/jpeg"),
    )

    assert response.status_code == 406
    assert "application/pdf" in response.json()["issue"][0]["diagnostics"]


def test_dicom_router_returns_dicom_file(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/dicom/ia-doc-image-01.dcm",
        headers=medmij_headers(medmij_request_id),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/dicom"
    assert len(response.content) > 1024


def test_dicom_router_returns_404_for_unknown_file(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/dicom/does-not-exist.dcm",
        headers=medmij_headers(medmij_request_id),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "The DICOM file 'does-not-exist' is not supported by the mock server"
    }


def test_wado_study_series_returns_dicom_json_metadata(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/dicom+json"

    payload = response.json()
    assert len(payload) == 4
    assert all(
        entry["0020000D"]["Value"][0] == REPRESENTATIVE_STUDY_UID for entry in payload
    )
    assert all("00080060" in entry for entry in payload)
    assert all("0008103E" in entry for entry in payload)
    assert all(
        entry["00081190"]["Value"][0].startswith(
            f"http://testserver/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series/"
        )
        for entry in payload
    )


def test_wado_study_series_rejects_application_dicom_accept(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series",
        headers=medmij_headers(medmij_request_id, "application/dicom"),
    )

    assert response.status_code == 406


def test_wado_study_metadata_rejects_application_dicom_accept(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/metadata",
        headers=medmij_headers(medmij_request_id, "application/dicom"),
    )

    assert response.status_code == 406


def test_wado_study_metadata_returns_instance_level_entries(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/metadata",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/dicom+json"

    payload = response.json()
    assert len(payload) == 4
    assert all("00080018" in entry for entry in payload)
    assert all("0020000E" in entry for entry in payload)


def test_wado_routes_reject_unsupported_accept_header(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/metadata",
        headers=medmij_headers(medmij_request_id, "text/plain"),
    )

    assert response.status_code == 406
    assert "application/dicom" in response.json()["detail"]
    assert "application/dicom+json" in response.json()["detail"]


def test_wado_study_and_series_retrieve_return_multipart_related(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    study_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}",
        headers=medmij_headers(
            medmij_request_id, 'multipart/related; type="application/dicom"'
        ),
    )

    assert study_response.status_code == 200
    assert study_response.headers["content-type"].startswith("multipart/related")
    assert study_response.content.count(b"Content-Type: application/dicom") == 4

    manifest_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )
    series_uid = manifest_response.json()[0]["0020000E"]["Value"][0]

    series_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series/{series_uid}",
        headers=medmij_headers(
            medmij_request_id, 'multipart/related; type="application/dicom"'
        ),
    )

    assert series_response.status_code == 200
    assert series_response.headers["content-type"].startswith("multipart/related")
    assert series_response.content.count(b"Content-Type: application/dicom") == 1


def test_wado_series_metadata_route_returns_instance_entries(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    manifest_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )
    series_uid = manifest_response.json()[0]["0020000E"]["Value"][0]

    metadata_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series/{series_uid}/metadata",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )

    assert metadata_response.status_code == 200
    assert metadata_response.headers["content-type"] == "application/dicom+json"
    assert len(metadata_response.json()) == 1
    assert metadata_response.json()[0]["0020000E"]["Value"][0] == series_uid


def test_wado_instance_and_rendered_routes_work(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    study_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )
    series_uid = study_response.json()[0]["0020000E"]["Value"][0]

    instances_response = test_client.get(
        f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}/series/{series_uid}/instances",
        headers=medmij_headers(medmij_request_id, "application/dicom+json"),
    )

    assert instances_response.status_code == 200
    assert instances_response.headers["content-type"] == "application/dicom+json"

    instance_uid = instances_response.json()[0]["00080018"]["Value"][0]

    dicom_response = test_client.get(
        (
            f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}"
            f"/series/{series_uid}/instances/{instance_uid}"
        ),
        headers=medmij_headers(medmij_request_id, "application/dicom"),
    )

    assert dicom_response.status_code == 200
    assert dicom_response.headers["content-type"] == "application/dicom"
    assert len(dicom_response.content) > 1024

    rendered_response = test_client.get(
        (
            f"/9000002/wado/studies/{REPRESENTATIVE_STUDY_UID}"
            f"/series/{series_uid}/instances/{instance_uid}/rendered"
        ),
        headers=medmij_headers(medmij_request_id, "image/jpeg"),
    )

    assert rendered_response.status_code == 200
    assert rendered_response.headers["content-type"] == "image/jpeg"
    assert len(rendered_response.content) > 1024


def test_only_one_patient_resource_remains_for_image_availability() -> None:
    resource_patients = sorted(
        path.name
        for path in Path("fhir/resources/ImageAvailability").glob("Patient-*.json")
    )
    demo_patients = sorted(
        path.name
        for path in Path("fhir/resources/demo/ImageAvailability").glob("Patient-*.json")
    )

    assert resource_patients == ["Patient-ia-patient.json"]
    assert demo_patients == ["Patient-ia-patient.json"]


def test_service_specific_reads_reject_wrong_fhir_version(
    test_client: TestClient,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        "/9000002/fhir/DocumentReference/ia-doc-report-01",
        headers=medmij_headers(
            medmij_request_id, "application/fhir+json; fhirVersion=3.0"
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-supported",
                "diagnostics": "The 'Accept' header value: 'application/fhir+json; fhirVersion=3.0' is not supported. Supported value: 'application/fhir+json; fhirVersion=4.0'",
            }
        ],
    }
