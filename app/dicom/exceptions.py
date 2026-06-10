from collections.abc import Iterable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DicomError(Exception):
    """Base exception for DICOM domain errors."""


class DicomNotFoundError(DicomError):
    """Raised when a requested DICOM resource cannot be found."""


class DicomFrameNotFoundError(DicomNotFoundError):
    """Raised when a requested rendered frame is unavailable."""


class DicomRenderingError(DicomError):
    """Raised when DICOM pixel data cannot be rendered."""


class DicomRepresentationNotSupportedError(DicomError):
    def __init__(self, supported_media_types: Iterable[str]) -> None:
        self.supported_media_types = tuple(sorted(supported_media_types))
        super().__init__(
            "The requested representation is not supported by the mock server. "
            f"Supported values: {', '.join(self.supported_media_types)}"
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DicomRepresentationNotSupportedError)
    async def dicom_representation_not_supported_handler(
        _: Request, exc: DicomRepresentationNotSupportedError
    ) -> JSONResponse:
        return JSONResponse(status_code=406, content={"detail": str(exc)})

    @app.exception_handler(DicomNotFoundError)
    async def dicom_not_found_handler(
        _: Request, exc: DicomNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DicomRenderingError)
    async def dicom_rendering_error_handler(
        _: Request, exc: DicomRenderingError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(DicomError)
    async def dicom_error_handler(_: Request, __: DicomError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Unexpected DICOM server error"},
        )
