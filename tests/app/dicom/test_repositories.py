from pathlib import Path

import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, UID

from app.dicom.exceptions import DicomNotFoundError
from app.dicom.repositories import DicomRepository


@pytest.fixture
def sample_dicom_file(tmp_path: Path) -> Path:
    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\x00\x01"
    file_meta.MediaStorageSOPClassUID = UID("1.2.840.10008.5.1.4.1.1.2")
    file_meta.MediaStorageSOPInstanceUID = UID("1.2.3.4.5")
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = UID("1.2.3.4")

    dicom_path = tmp_path / "test.dcm"
    dataset = FileDataset(
        str(dicom_path), {}, file_meta=file_meta, preamble=b"\x00" * 128
    )
    dataset.PatientName = "Test^Patient"
    dataset.PatientID = "123456"
    dataset.StudyInstanceUID = "1.2.3.4.5"
    dataset.SeriesInstanceUID = "1.2.3.4.5.1"
    dataset.SOPInstanceUID = "1.2.3.4.5.1.1"
    dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    dataset.Modality = "CT"
    dataset.StudyDescription = "Test Study"
    dataset.SeriesDescription = "Test Series"
    dataset.BodyPartExamined = "CHEST"
    dataset.save_as(str(dicom_path))
    return dicom_path


@pytest.fixture
def repository(sample_dicom_file: Path) -> DicomRepository:
    return DicomRepository(sample_dicom_file.parent)


def test_get_registry_returns_cached_object(repository: DicomRepository) -> None:
    assert repository.get_registry() is repository.get_registry()


def test_get_instance_by_document_id_returns_matching_instance(
    repository: DicomRepository,
) -> None:
    instance = repository.get_instance_by_document_id("test")

    assert instance.document_id == "test"
    assert instance.study_uid == "1.2.3.4.5"
    assert instance.series_uid == "1.2.3.4.5.1"


@pytest.mark.parametrize(
    ("method_name", "args", "expected_message"),
    [
        ("get_instance_by_document_id", ("missing",), "missing"),
        ("get_study_instances", ("missing-study",), "missing-study"),
        ("get_series_instances", ("1.2.3.4.5", "missing-series"), "missing-series"),
        (
            "get_instance_by_uids",
            ("1.2.3.4.5", "1.2.3.4.5.1", "missing-instance"),
            "missing-instance",
        ),
    ],
)
def test_lookup_methods_raise_for_missing_values(
    repository: DicomRepository,
    method_name: str,
    args: tuple[str, ...],
    expected_message: str,
) -> None:
    method = getattr(repository, method_name)

    with pytest.raises(DicomNotFoundError, match=expected_message):
        method(*args)


def test_get_study_instances_returns_all_instances(repository: DicomRepository) -> None:
    instances = repository.get_study_instances("1.2.3.4.5")

    assert len(instances) == 1
    assert instances[0].study_uid == "1.2.3.4.5"


def test_get_series_instances_returns_series_instances(
    repository: DicomRepository,
) -> None:
    instances = repository.get_series_instances("1.2.3.4.5", "1.2.3.4.5.1")

    assert len(instances) == 1
    assert instances[0].series_uid == "1.2.3.4.5.1"


def test_get_instance_by_uids_returns_matching_instance(
    repository: DicomRepository,
) -> None:
    instance = repository.get_instance_by_uids(
        "1.2.3.4.5", "1.2.3.4.5.1", "1.2.3.4.5.1.1"
    )

    assert instance.instance_uid == "1.2.3.4.5.1.1"


@pytest.mark.parametrize("stop_before_pixels", [False, True])
def test_read_dataset_returns_pydicom_dataset(
    repository: DicomRepository,
    stop_before_pixels: bool,
) -> None:
    dataset = repository.read_dataset(
        repository.get_instance_by_document_id("test"),
        stop_before_pixels=stop_before_pixels,
    )

    assert dataset.PatientName == "Test^Patient"
    assert dataset.Modality == "CT"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("valid", "valid"), (None, None), ("   ", None), ("  content  ", "content")],
)
def test_dicom_field_to_optional_str_normalizes_values(
    value: object, expected: str | None
) -> None:
    assert DicomRepository._dicom_field_to_optional_str(value) == expected


def test_registry_indexes_instances_by_lookup_key(repository: DicomRepository) -> None:
    registry = repository.get_registry()

    assert "test" in registry.by_document_id
    assert "1.2.3.4.5" in registry.by_study_uid
    assert ("1.2.3.4.5", "1.2.3.4.5.1") in registry.by_series_key
