from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DicomInstance:
    document_id: str
    path: Path
    study_uid: str
    series_uid: str
    instance_uid: str
    sop_class_uid: str
    number_of_frames: int
    modality: str
    study_description: str | None
    series_description: str | None
    body_part_examined: str | None


@dataclass(frozen=True)
class DicomRegistry:
    by_document_id: dict[str, DicomInstance]
    by_study_uid: dict[str, tuple[DicomInstance, ...]]
    by_series_key: dict[tuple[str, str], tuple[DicomInstance, ...]]
    by_instance_key: dict[tuple[str, str, str], DicomInstance]


@dataclass(frozen=True)
class MultipartDicomPayload:
    boundary: str
    content: bytes
