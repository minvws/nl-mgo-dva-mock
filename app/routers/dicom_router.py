from fastapi import APIRouter, Header, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.dicom.services import DicomRouteHandler
from app.hcim.constants import MEDMIJ_REQUEST_ID_HEADER
from app.utils import resolve_instance

router = APIRouter()


@router.get("/9000002/dicom/{document_id}.dcm")
def show_dicom(
    document_id: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> FileResponse:
    return dicom_route_handler.handle_dicom(
        document_id, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}/series")
def show_study_series_manifest(
    study_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_study_series_manifest(
        study_uid, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}/metadata")
def show_study_metadata(
    study_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_study_metadata(
        study_uid, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}")
def show_study(
    study_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_study(
        study_uid, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}/series/{series_uid}")
def show_series(
    study_uid: str,
    series_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_series(
        study_uid, series_uid, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}/series/{series_uid}/metadata")
def show_series_metadata(
    study_uid: str,
    series_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> JSONResponse:
    return dicom_route_handler.handle_series_metadata(
        study_uid, series_uid, request, accept_header, medmij_request_id
    )


@router.get("/9000002/wado/studies/{study_uid}/series/{series_uid}/instances")
def show_series_instances_metadata(
    study_uid: str,
    series_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> JSONResponse:
    return dicom_route_handler.handle_series_metadata(
        study_uid, series_uid, request, accept_header, medmij_request_id
    )


@router.get(
    "/9000002/wado/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
)
def show_instance(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> FileResponse:
    return dicom_route_handler.handle_instance(
        study_uid, series_uid, instance_uid, request, accept_header, medmij_request_id
    )


@router.get(
    "/9000002/wado/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_id:int}/rendered"
)
def show_instance_frame_rendered(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    request: Request,
    frame_id: int,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_instance_rendered(
        study_uid,
        series_uid,
        instance_uid,
        request,
        accept_header,
        medmij_request_id,
        frame_id,
    )


@router.get(
    "/9000002/wado/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered"
)
def show_instance_rendered(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    request: Request,
    accept_header: str | None = Header(None, alias="Accept"),
    medmij_request_id: str = Header(..., alias=MEDMIJ_REQUEST_ID_HEADER),
    dicom_route_handler: DicomRouteHandler = resolve_instance(DicomRouteHandler),
) -> Response:
    return dicom_route_handler.handle_instance_rendered(
        study_uid,
        series_uid,
        instance_uid,
        request,
        accept_header,
        medmij_request_id,
        None,
    )
