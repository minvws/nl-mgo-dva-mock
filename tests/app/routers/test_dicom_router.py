from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

STUDY_UID = "1.2.752.24.7.3059655634.36522"


@pytest.fixture
def resolved_ids(
    test_client: TestClient,
    medmij_request_id: str,
) -> dict[str, str]:
    series_data = test_client.get(
        f"/9000002/wado/studies/{STUDY_UID}/series",
        headers={
            "Accept": "application/dicom+json",
            "MedMij-Request-ID": medmij_request_id,
        },
    ).json()
    series_uid = series_data[0]["0020000E"]["Value"][0]
    instances_data = test_client.get(
        f"/9000002/wado/studies/{STUDY_UID}/series/{series_uid}/instances",
        headers={
            "Accept": "application/dicom+json",
            "MedMij-Request-ID": medmij_request_id,
        },
    ).json()
    instance_uid = instances_data[0]["00080018"]["Value"][0]
    return {"series_uid": series_uid, "instance_uid": instance_uid}


@pytest.mark.parametrize(
    ("path", "accept_header", "expected_content_type_prefix"),
    [
        (
            f"/9000002/dicom/ia-doc-image-01.dcm",
            "application/dicom",
            "application/dicom",
        ),
        (
            f"/9000002/wado/studies/{STUDY_UID}/series",
            "application/dicom+json",
            "application/dicom+json",
        ),
        (
            f"/9000002/wado/studies/{STUDY_UID}/metadata",
            "application/dicom+json",
            "application/dicom+json",
        ),
        (
            f"/9000002/wado/studies/{STUDY_UID}",
            'multipart/related; type="application/dicom"',
            "multipart/related",
        ),
    ],
)
def test_static_dicom_routes_return_successful_responses(
    test_client: TestClient,
    path: str,
    accept_header: str,
    expected_content_type_prefix: str,
    medmij_request_id: str,
) -> None:
    response = test_client.get(
        path,
        headers={"Accept": accept_header, "MedMij-Request-ID": medmij_request_id},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(expected_content_type_prefix)


def test_series_and_instance_routes_return_successful_responses(
    test_client: TestClient,
    resolved_ids: dict[str, str],
    medmij_request_id: str,
) -> None:
    series_uid = resolved_ids["series_uid"]
    instance_uid = resolved_ids["instance_uid"]
    base = f"/9000002/wado/studies/{STUDY_UID}/series/{series_uid}"

    cases = [
        (f"{base}", 'multipart/related; type="application/dicom"', "multipart/related"),
        (f"{base}/metadata", "application/dicom+json", "application/dicom+json"),
        (f"{base}/instances", "application/dicom+json", "application/dicom+json"),
        (f"{base}/instances/{instance_uid}", "application/dicom", "application/dicom"),
        (f"{base}/instances/{instance_uid}/rendered", "image/jpeg", "image/jpeg"),
        (
            f"{base}/instances/{instance_uid}/frames/1/rendered",
            "image/jpeg",
            "image/jpeg",
        ),
    ]

    for path, accept_header, expected_prefix in cases:
        response = test_client.get(
            path,
            headers={
                "Accept": accept_header,
                "MedMij-Request-ID": medmij_request_id,
            },
        )
        assert response.status_code == 200, (
            f"Expected 200 for {path}, got {response.status_code}"
        )
        assert response.headers["content-type"].startswith(expected_prefix)


def test_dicom_endpoint_returns_422_without_medmij_request_id(
    test_client: TestClient,
) -> None:
    response = test_client.get(
        "/9000002/dicom/ia-doc-image-01.dcm",
        headers={"Accept": "application/dicom"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["header", "MedMij-Request-ID"]
