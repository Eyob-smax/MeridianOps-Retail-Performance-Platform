from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import Response as RawResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request, forbidden
from app.db.session import get_db
from app.schemas.analytics import (
    DashboardCreateRequest,
    DashboardDetailResponse,
    DashboardSummaryResponse,
    DashboardUpdateRequest,
    ShareLinkCreateRequest,
    ShareLinkResponse,
    SharedDashboardResponse,
)
from app.schemas.analytics_extra import (
    DashboardAuditEntry,
    DashboardAuditFeedResponse,
    DateDrillDownResponse,
    DrillDownResponse,
    ExportMetadataResponse,
)
from app.schemas.auth import AuthUser
from app.services.analytics_service import (
    DashboardNotFoundError,
    DashboardPermissionError,
    ExportError,
    SharedLinkNotFoundError,
    create_dashboard,
    create_share_link,
    deactivate_share_link,
    delete_dashboard,
    export_dashboard,
    get_dashboard_audit_rows,
    get_dashboard_detail,
    list_dashboards,
    list_share_links,
    record_export_audit,
    resolve_shared_dashboard,
    update_dashboard,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_MANAGER_ROLES = {"administrator", "store_manager"}
_FRONTEND_BASE_URL = "http://localhost:5173"


def _parse_store_ids(store_ids: str | None) -> list[int] | None:
    if store_ids is None:
        return None
    values = [chunk.strip() for chunk in store_ids.split(",") if chunk.strip()]
    if not values:
        return None
    parsed: list[int] = []
    for value in values:
        try:
            parsed.append(int(value))
        except ValueError as exc:
            raise bad_request("store_ids must be comma-separated integers") from exc
    return parsed


def _handle_dashboard_error(exc: Exception):
    if isinstance(exc, DashboardPermissionError):
        raise forbidden(str(exc))
    if isinstance(exc, DashboardNotFoundError):
        raise bad_request(str(exc))
    if isinstance(exc, SharedLinkNotFoundError):
        raise bad_request(str(exc))
    if isinstance(exc, ExportError):
        raise bad_request(str(exc))
    if isinstance(exc, ValueError):
        raise bad_request(str(exc))
    raise exc


@router.get("/dashboards", response_model=list[DashboardSummaryResponse])
def dashboard_list(
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DashboardSummaryResponse]:
    try:
        return list_dashboards(db, current_user)
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.post("/dashboards", response_model=DashboardDetailResponse)
def dashboard_create(
    payload: DashboardCreateRequest,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardDetailResponse:
    try:
        response = create_dashboard(db, payload, current_user)
        db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}", response_model=DashboardDetailResponse)
def dashboard_detail(
    dashboard_id: int,
    store_ids: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardDetailResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        return get_dashboard_detail(
            db,
            dashboard_id,
            current_user=current_user,
            requested_store_ids=requested_store_ids,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.patch("/dashboards/{dashboard_id}", response_model=DashboardDetailResponse)
def dashboard_patch(
    dashboard_id: int,
    payload: DashboardUpdateRequest,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardDetailResponse:
    try:
        response = update_dashboard(db, dashboard_id, payload, current_user)
        db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def dashboard_delete(
    dashboard_id: int,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_dashboard(db, dashboard_id, current_user)
        db.commit()
        return Response(status_code=204)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/drilldown/store/{store_id}", response_model=DrillDownResponse)
def dashboard_store_drilldown(
    dashboard_id: int,
    store_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DrillDownResponse:
    try:
        detail = get_dashboard_detail(
            db,
            dashboard_id,
            current_user=current_user,
            requested_store_ids=[store_id],
            start_date=start_date,
            end_date=end_date,
        )
        if not detail.data.by_store:
            raise bad_request("No data available for selected store")
        aggregate = detail.data.by_store[0]
        return DrillDownResponse(
            dashboard_id=detail.id,
            store_id=aggregate.store_id,
            store_name=aggregate.store_name,
            start_date=detail.data.filters.start_date,
            end_date=detail.data.filters.end_date,
            orders=aggregate.orders,
            revenue=aggregate.revenue,
            refunds=aggregate.refunds,
            cost=aggregate.cost,
            gross_margin=aggregate.gross_margin,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/drilldown/date/{business_date}", response_model=DateDrillDownResponse)
def dashboard_date_drilldown(
    dashboard_id: int,
    business_date: date,
    store_ids: str | None = Query(default=None),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DateDrillDownResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        detail = get_dashboard_detail(
            db,
            dashboard_id,
            current_user=current_user,
            requested_store_ids=requested_store_ids,
            start_date=business_date,
            end_date=business_date,
        )
        if not detail.data.by_date:
            raise bad_request("No data available for selected date")
        aggregate = detail.data.by_date[0]
        return DateDrillDownResponse(
            dashboard_id=detail.id,
            business_date=aggregate.business_date,
            start_date=detail.data.filters.start_date,
            end_date=detail.data.filters.end_date,
            orders=aggregate.orders,
            revenue=aggregate.revenue,
            refunds=aggregate.refunds,
            cost=aggregate.cost,
            gross_margin=aggregate.gross_margin,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/export")
def dashboard_export(
    dashboard_id: int,
    format: str = Query(pattern="^(csv|png|pdf)$"),
    store_ids: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RawResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        detail = get_dashboard_detail(
            db,
            dashboard_id,
            current_user=current_user,
            requested_store_ids=requested_store_ids,
            start_date=start_date,
            end_date=end_date,
        )
        filename, content_type, data = export_dashboard(
            format_name=format,
            dashboard_name=detail.name,
            data=detail.data,
        )
        record_export_audit(
            db,
            actor_user_id=current_user.id,
            dashboard_id=detail.id,
            format_name=format,
            file_size=len(data),
        )
        db.commit()
        return RawResponse(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/export/metadata", response_model=ExportMetadataResponse)
def dashboard_export_metadata(
    dashboard_id: int,
    format: str = Query(pattern="^(csv|png|pdf)$"),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportMetadataResponse:
    try:
        detail = get_dashboard_detail(
            db,
            dashboard_id,
            current_user=current_user,
            requested_store_ids=None,
            start_date=None,
            end_date=None,
        )
        filename, content_type, data = export_dashboard(
            format_name=format,
            dashboard_name=detail.name,
            data=detail.data,
        )
        return ExportMetadataResponse(filename=filename, content_type=content_type, size_bytes=len(data))
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/audit", response_model=DashboardAuditFeedResponse)
def dashboard_audit(
    dashboard_id: int,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardAuditFeedResponse:
    try:
        entries = get_dashboard_audit_rows(db, dashboard_id, current_user)
        return DashboardAuditFeedResponse(
            entries=[
                DashboardAuditEntry(
                    id=entry.id,
                    action=entry.action,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    actor_user_id=entry.actor_user_id,
                    detail_json=entry.detail_json,
                    created_at=entry.created_at.isoformat(),
                )
                for entry in entries
            ]
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.post("/dashboards/{dashboard_id}/share-links", response_model=ShareLinkResponse)
def dashboard_share_link_create(
    dashboard_id: int,
    payload: ShareLinkCreateRequest,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareLinkResponse:
    try:
        response = create_share_link(db, dashboard_id, payload, current_user, _FRONTEND_BASE_URL)
        db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/dashboards/{dashboard_id}/share-links", response_model=list[ShareLinkResponse])
def dashboard_share_link_list(
    dashboard_id: int,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShareLinkResponse]:
    try:
        return list_share_links(db, dashboard_id, current_user, _FRONTEND_BASE_URL)
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.delete("/dashboards/{dashboard_id}/share-links/{link_id}", status_code=204)
def dashboard_share_link_delete(
    dashboard_id: int,
    link_id: int,
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        deactivate_share_link(db, dashboard_id, link_id, current_user)
        db.commit()
        return Response(status_code=204)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/shared/{token}", response_model=SharedDashboardResponse)
def shared_dashboard_view(
    token: str,
    store_ids: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SharedDashboardResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        response = resolve_shared_dashboard(
            db,
            token,
            requested_store_ids=requested_store_ids,
            start_date=start_date,
            end_date=end_date,
        )
        db.commit()
        return response
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/shared/{token}/export")
def shared_dashboard_export(
    token: str,
    format: str = Query(pattern="^(csv|png|pdf)$"),
    store_ids: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RawResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        shared = resolve_shared_dashboard(
            db,
            token,
            requested_store_ids=requested_store_ids,
            start_date=start_date,
            end_date=end_date,
        )
        filename, content_type, data = export_dashboard(
            format_name=format,
            dashboard_name=shared.name,
            data=shared.data,
        )
        record_export_audit(
            db,
            actor_user_id=None,
            dashboard_id=shared.dashboard_id,
            format_name=format,
            file_size=len(data),
            shared_token=token,
        )
        db.commit()
        return RawResponse(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _handle_dashboard_error(exc)


@router.get("/shared/{token}/drilldown/store/{store_id}", response_model=DrillDownResponse)
def shared_dashboard_store_drilldown(
    token: str,
    store_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DrillDownResponse:
    try:
        shared = resolve_shared_dashboard(
            db,
            token,
            requested_store_ids=[store_id],
            start_date=start_date,
            end_date=end_date,
        )
        if not shared.data.by_store:
            raise bad_request("No data available for selected store")
        aggregate = shared.data.by_store[0]
        return DrillDownResponse(
            dashboard_id=shared.dashboard_id,
            store_id=aggregate.store_id,
            store_name=aggregate.store_name,
            start_date=shared.data.filters.start_date,
            end_date=shared.data.filters.end_date,
            orders=aggregate.orders,
            revenue=aggregate.revenue,
            refunds=aggregate.refunds,
            cost=aggregate.cost,
            gross_margin=aggregate.gross_margin,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.get("/shared/{token}/drilldown/date/{business_date}", response_model=DateDrillDownResponse)
def shared_dashboard_date_drilldown(
    token: str,
    business_date: date,
    store_ids: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DateDrillDownResponse:
    try:
        requested_store_ids = _parse_store_ids(store_ids)
        shared = resolve_shared_dashboard(
            db,
            token,
            requested_store_ids=requested_store_ids,
            start_date=business_date,
            end_date=business_date,
        )
        if not shared.data.by_date:
            raise bad_request("No data available for selected date")
        aggregate = shared.data.by_date[0]
        return DateDrillDownResponse(
            dashboard_id=shared.dashboard_id,
            business_date=aggregate.business_date,
            start_date=shared.data.filters.start_date,
            end_date=shared.data.filters.end_date,
            orders=aggregate.orders,
            revenue=aggregate.revenue,
            refunds=aggregate.refunds,
            cost=aggregate.cost,
            gross_margin=aggregate.gross_margin,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.get("/shared/{token}/export/metadata", response_model=ExportMetadataResponse)
def shared_dashboard_export_metadata(
    token: str,
    format: str = Query(pattern="^(csv|png|pdf)$"),
    db: Session = Depends(get_db),
) -> ExportMetadataResponse:
    try:
        shared = resolve_shared_dashboard(
            db,
            token,
            requested_store_ids=None,
            start_date=None,
            end_date=None,
        )
        filename, content_type, data = export_dashboard(
            format_name=format,
            dashboard_name=shared.name,
            data=shared.data,
        )
        return ExportMetadataResponse(filename=filename, content_type=content_type, size_bytes=len(data))
    except Exception as exc:  # noqa: BLE001
        _handle_dashboard_error(exc)


@router.post("/shared/{token}/save", status_code=403)
def shared_dashboard_save_forbidden(token: str) -> None:
    raise forbidden("Shared dashboards are read-only")


@router.patch("/shared/{token}", status_code=403)
def shared_dashboard_patch_forbidden(token: str) -> None:
    raise forbidden("Shared dashboards are read-only")


@router.post("/shared/{token}/share-links", status_code=403)
def shared_dashboard_create_share_link_forbidden(token: str) -> None:
    raise forbidden("Shared dashboards are read-only")


@router.delete("/shared/{token}", status_code=403)
def shared_dashboard_delete_forbidden(token: str) -> None:
    raise forbidden("Shared dashboards are read-only")
