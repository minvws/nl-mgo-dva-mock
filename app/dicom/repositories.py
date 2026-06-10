from collections import defaultdict
from pathlib import Path
from typing import Any

import pydicom
from pydicom.dataset import Dataset

from app.dicom.constants import DICOM_DIRECTORY
from app.dicom.exceptions import DicomNotFoundError
from app.dicom.schemas import DicomInstance, DicomRegistry


class DicomRepository:
    def __init__(self, dicom_directory: Path = DICOM_DIRECTORY) -> None:
        self._dicom_directory = dicom_directory
        self._registry: DicomRegistry | None = None

    def get_registry(self) -> DicomRegistry:
        if self._registry is not None:
            return self._registry

        by_document_id: dict[str, DicomInstance] = {}
        study_buckets: defaultdict[str, list[DicomInstance]] = defaultdict(list)
        series_buckets: defaultdict[tuple[str, str], list[DicomInstance]] = defaultdict(
            list
        )
        by_instance_key: dict[tuple[str, str, str], DicomInstance] = {}

        for dicom_path in sorted(self._dicom_directory.glob("*.dcm")):
            dataset = pydicom.dcmread(dicom_path, stop_before_pixels=True)
            instance = DicomInstance(
                document_id=dicom_path.stem,
                path=dicom_path,
                study_uid=str(dataset.StudyInstanceUID),
                series_uid=str(dataset.SeriesInstanceUID),
                instance_uid=str(dataset.SOPInstanceUID),
                sop_class_uid=str(dataset.SOPClassUID),
                number_of_frames=int(str(getattr(dataset, "NumberOfFrames", 1) or 1)),
                modality=str(getattr(dataset, "Modality", "")),
                study_description=self._dicom_field_to_optional_str(
                    getattr(dataset, "StudyDescription", None)
                ),
                series_description=self._dicom_field_to_optional_str(
                    getattr(dataset, "SeriesDescription", None)
                ),
                body_part_examined=self._dicom_field_to_optional_str(
                    getattr(dataset, "BodyPartExamined", None)
                ),
            )
            by_document_id[instance.document_id] = instance
            study_buckets[instance.study_uid].append(instance)
            series_buckets[(instance.study_uid, instance.series_uid)].append(instance)
            by_instance_key[
                (instance.study_uid, instance.series_uid, instance.instance_uid)
            ] = instance

        self._registry = DicomRegistry(
            by_document_id=by_document_id,
            by_study_uid={
                study_uid: tuple(sorted(instances, key=lambda item: item.series_uid))
                for study_uid, instances in study_buckets.items()
            },
            by_series_key={
                series_key: tuple(sorted(instances, key=lambda item: item.instance_uid))
                for series_key, instances in series_buckets.items()
            },
            by_instance_key=by_instance_key,
        )
        return self._registry

    def get_instance_by_document_id(self, document_id: str) -> DicomInstance:
        instance = self.get_registry().by_document_id.get(document_id)
        if instance is None:
            raise DicomNotFoundError(
                f"The DICOM file '{document_id}' is not supported by the mock server"
            )
        return instance

    def get_study_instances(self, study_uid: str) -> tuple[DicomInstance, ...]:
        study_instances = self.get_registry().by_study_uid.get(study_uid)
        if study_instances is None:
            raise DicomNotFoundError(
                f"The study '{study_uid}' is not supported by the mock server"
            )
        return study_instances

    def get_series_instances(
        self, study_uid: str, series_uid: str
    ) -> tuple[DicomInstance, ...]:
        series_instances = self.get_registry().by_series_key.get(
            (study_uid, series_uid)
        )
        if series_instances is None:
            raise DicomNotFoundError(
                "The series "
                f"'{series_uid}' in study '{study_uid}' is not supported by the mock server"
            )
        return series_instances

    def get_instance_by_uids(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> DicomInstance:
        instance = self.get_registry().by_instance_key.get(
            (study_uid, series_uid, instance_uid)
        )
        if instance is None:
            raise DicomNotFoundError(
                "The DICOM instance "
                f"'{instance_uid}' in series '{series_uid}' and study '{study_uid}' "
                "is not supported by the mock server"
            )
        return instance

    def read_dataset(
        self, instance: DicomInstance, stop_before_pixels: bool = False
    ) -> Dataset:
        return pydicom.dcmread(instance.path, stop_before_pixels=stop_before_pixels)

    @staticmethod
    def _dicom_field_to_optional_str(value: Any) -> str | None:
        """
        Normalize a DICOM field value to a string, or None if empty.
        Args:
            value: A DICOM field value (may be DataElement, str, None, etc.)
        Returns:
            Normalized string value, or None if value was None or empty after normalization.
        """
        if value is None:
            return None

        string_value = str(value).strip()
        return string_value or None
