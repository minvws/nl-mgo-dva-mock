from pathlib import Path
from typing import Final

from pydicom.uid import UID

from app.utils import root_path

DICOM_DIRECTORY: Final[Path] = Path(root_path("static/imageavailability/dicom"))
DICOM_JSON_MEDIA_TYPES: Final[set[str]] = {"application/dicom+json"}
DICOM_MEDIA_TYPES: Final[set[str]] = {"application/dicom"}
MULTIPART_DICOM_MEDIA_TYPES: Final[set[str]] = {
    "multipart/related",
}
JPEG_MEDIA_TYPES: Final[set[str]] = {"image/jpeg"}
KOS_SOP_CLASS_UID: Final[UID] = UID("1.2.840.10008.5.1.4.1.1.88.59")
