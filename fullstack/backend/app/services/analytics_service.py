import csv
import io
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from secrets import token_urlsafe
from typing import Iterable

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog, DashboardLayout, DashboardShareLink
from app.schemas.analytics import (
    DashboardCreateRequest,
    DashboardDataPayload,
    DashboardDataRow,
    DashboardDateAggregate,
    DashboardDetailResponse,
    DashboardFilters,
    DashboardStoreAggregate,
    DashboardSummaryResponse,
    DashboardTotals,
    DashboardUpdateRequest,
    ShareLinkCreateRequest,
    ShareLinkResponse,
    SharedDashboardResponse,
    StoreOption,
)
from app.schemas.auth import AuthUser
from app.services.audit_service import audit_event

STORE_NAMES = {
    101: "Downtown",
    102: "Airport",
    103: "West End",
    104: "North Hub",
    105: "Harbor",
    106: "University",
}

DEFAULT_LOOKBACK_DAYS = 14
logger = logging.getLogger("meridianops.analytics")


class DashboardPermissionError(ValueError):
    pass


class DashboardNotFoundError(ValueError):
    pass


class SharedLinkNotFoundError(ValueError):
    pass


class ExportError(ValueError):
    pass


def _unique_ints(values: Iterable[int]) -> list[int]:
    return sorted({int(value) for value in values})


def _default_store_ids() -> list[int]:
    return sorted(STORE_NAMES.keys())


def _store_options(store_ids: list[int]) -> list[StoreOption]:
    return [StoreOption(id=store_id, name=STORE_NAMES.get(store_id, f"Store {store_id}")) for store_id in store_ids]


def _as_json(values: list[int]) -> str:
    return json.dumps(_unique_ints(values), separators=(",", ":"))


def _from_json(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    output: list[int] = []
    for value in parsed:
        try:
            output.append(int(value))
        except (TypeError, ValueError):
            continue
    return _unique_ints(output)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scope_for_role(current_user: AuthUser) -> list[int]:
    if "administrator" in current_user.roles:
        return _default_store_ids()
    if "store_manager" in current_user.roles:
        return [101, 102, 103]
    raise DashboardPermissionError("Insufficient permissions")


def _intersection(left: list[int], right: list[int]) -> list[int]:
    return sorted(set(left).intersection(set(right)))


def _resolve_window(
    *,
    requested_start: date | None,
    requested_end: date | None,
    default_start: date | None,
    default_end: date | None,
) -> tuple[date, date]:
    today = date.today()
    end_date = requested_end or default_end or today
    start_date = requested_start or default_start or (end_date - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1))
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    return start_date, end_date


def _metric_seed(store_id: int, business_date: date) -> int:
    return (store_id * 97) + business_date.toordinal()


def _build_rows(store_ids: list[int], start_date: date, end_date: date) -> list[DashboardDataRow]:
    rows: list[DashboardDataRow] = []
    current = start_date
    while current <= end_date:
        for store_id in store_ids:
            seed = _metric_seed(store_id, current)
            orders = 25 + (seed % 32)
            revenue = Decimal(orders * (18 + (seed % 7))) + Decimal((seed % 100) / 100)
            refunds = (revenue * Decimal("0.03")).quantize(Decimal("0.01"))
            cost = (revenue * Decimal("0.58")).quantize(Decimal("0.01"))
            gross_margin = (revenue - refunds - cost).quantize(Decimal("0.01"))
            rows.append(
                DashboardDataRow(
                    store_id=store_id,
                    store_name=STORE_NAMES.get(store_id, f"Store {store_id}"),
                    business_date=current,
                    orders=orders,
                    revenue=revenue.quantize(Decimal("0.01")),
                    refunds=refunds,
                    cost=cost,
                    gross_margin=gross_margin,
                )
            )
        current += timedelta(days=1)
    return rows


def _aggregate(
    rows: list[DashboardDataRow],
) -> tuple[DashboardTotals, list[DashboardStoreAggregate], list[DashboardDateAggregate]]:
    totals_orders = 0
    totals_revenue = Decimal("0.00")
    totals_refunds = Decimal("0.00")
    totals_cost = Decimal("0.00")
    totals_margin = Decimal("0.00")

    by_store: dict[int, DashboardStoreAggregate] = {}
    by_date: dict[date, DashboardDateAggregate] = {}

    for row in rows:
        totals_orders += row.orders
        totals_revenue += row.revenue
        totals_refunds += row.refunds
        totals_cost += row.cost
        totals_margin += row.gross_margin

        store_bucket = by_store.get(row.store_id)
        if store_bucket is None:
            store_bucket = DashboardStoreAggregate(
                store_id=row.store_id,
                store_name=row.store_name,
                orders=0,
                revenue=Decimal("0.00"),
                refunds=Decimal("0.00"),
                cost=Decimal("0.00"),
                gross_margin=Decimal("0.00"),
            )
            by_store[row.store_id] = store_bucket
        store_bucket.orders += row.orders
        store_bucket.revenue += row.revenue
        store_bucket.refunds += row.refunds
        store_bucket.cost += row.cost
        store_bucket.gross_margin += row.gross_margin

        date_bucket = by_date.get(row.business_date)
        if date_bucket is None:
            date_bucket = DashboardDateAggregate(
                business_date=row.business_date,
                orders=0,
                revenue=Decimal("0.00"),
                refunds=Decimal("0.00"),
                cost=Decimal("0.00"),
                gross_margin=Decimal("0.00"),
            )
            by_date[row.business_date] = date_bucket
        date_bucket.orders += row.orders
        date_bucket.revenue += row.revenue
        date_bucket.refunds += row.refunds
        date_bucket.cost += row.cost
        date_bucket.gross_margin += row.gross_margin

    totals = DashboardTotals(
        orders=totals_orders,
        revenue=totals_revenue.quantize(Decimal("0.01")),
        refunds=totals_refunds.quantize(Decimal("0.01")),
        cost=totals_cost.quantize(Decimal("0.01")),
        gross_margin=totals_margin.quantize(Decimal("0.01")),
    )

    by_store_rows = list(by_store.values())
    by_store_rows.sort(key=lambda item: item.store_id)
    by_date_rows = list(by_date.values())
    by_date_rows.sort(key=lambda item: item.business_date)
    return totals, by_store_rows, by_date_rows


def _build_data_payload(store_ids: list[int], start_date: date, end_date: date) -> DashboardDataPayload:
    rows = _build_rows(store_ids, start_date, end_date)
    totals, by_store_rows, by_date_rows = _aggregate(rows)
    return DashboardDataPayload(
        filters=DashboardFilters(store_ids=store_ids, start_date=start_date, end_date=end_date),
        totals=totals,
        by_store=by_store_rows,
        by_date=by_date_rows,
        rows=rows,
    )


def _layout_widgets(layout: DashboardLayout):
    raw = json.loads(layout.layout_json)
    if not isinstance(raw, list):
        raise ValueError("Dashboard layout must be a list")
    return raw


def _dashboard_allowed_store_ids(layout: DashboardLayout) -> list[int]:
    configured = _from_json(layout.allowed_store_ids_json)
    return configured if configured else _default_store_ids()


def _dashboard_actor_visibility(layout: DashboardLayout, actor_scope_store_ids: list[int]) -> list[int]:
    return _intersection(_dashboard_allowed_store_ids(layout), actor_scope_store_ids)


def _scope_dashboard_store_ids(
    *,
    dashboard_store_ids: list[int],
    actor_scope_store_ids: list[int],
    requested_store_ids: list[int] | None,
) -> list[int]:
    store_ids = _intersection(dashboard_store_ids, actor_scope_store_ids)
    if requested_store_ids:
        store_ids = _intersection(store_ids, _unique_ints(requested_store_ids))
    if not store_ids:
        raise DashboardPermissionError("No permitted stores available for this dashboard")
    return store_ids


def _dashboard_summary(layout: DashboardLayout, visible_store_ids: list[int]) -> DashboardSummaryResponse:
    widgets = _layout_widgets(layout)
    return DashboardSummaryResponse(
        id=layout.id,
        name=layout.name,
        description=layout.description,
        widget_count=len(widgets),
        allowed_store_ids=visible_store_ids,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


def _get_dashboard_or_raise(db: Session, dashboard_id: int) -> DashboardLayout:
    layout = db.execute(
        select(DashboardLayout).where(DashboardLayout.id == dashboard_id, DashboardLayout.is_archived.is_(False))
    ).scalar_one_or_none()
    if not layout:
        raise DashboardNotFoundError("Dashboard not found")
    return layout


def create_dashboard(db: Session, payload: DashboardCreateRequest, current_user: AuthUser) -> DashboardDetailResponse:
    allowed_scope = _scope_for_role(current_user)
    requested_store_ids = _unique_ints(payload.allowed_store_ids) if payload.allowed_store_ids else allowed_scope
    scoped_store_ids = _intersection(requested_store_ids, allowed_scope)
    if not scoped_store_ids:
        raise DashboardPermissionError("Cannot create a dashboard without permitted stores")

    layout = DashboardLayout(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        layout_json=json.dumps([widget.model_dump() for widget in payload.widgets], separators=(",", ":")),
        allowed_store_ids_json=_as_json(scoped_store_ids),
        default_start_date=payload.default_start_date,
        default_end_date=payload.default_end_date,
        created_by_user_id=current_user.id,
        is_archived=False,
    )
    db.add(layout)
    db.flush()

    audit_event(
        db,
        action="dashboard.created",
        resource_type="dashboard",
        resource_id=str(layout.id),
        actor_user_id=current_user.id,
        detail={
            "name": layout.name,
            "widget_count": len(payload.widgets),
            "allowed_store_ids": scoped_store_ids,
        },
    )

    return get_dashboard_detail(
        db,
        layout.id,
        current_user=current_user,
        requested_store_ids=None,
        start_date=None,
        end_date=None,
    )


def list_dashboards(db: Session, current_user: AuthUser) -> list[DashboardSummaryResponse]:
    actor_scope = _scope_for_role(current_user)
    rows = db.execute(
        select(DashboardLayout).where(DashboardLayout.is_archived.is_(False)).order_by(DashboardLayout.updated_at.desc())
    ).scalars()

    response: list[DashboardSummaryResponse] = []
    for row in rows:
        visible_store_ids = _dashboard_actor_visibility(row, actor_scope)
        if not visible_store_ids:
            continue
        response.append(_dashboard_summary(row, visible_store_ids))
    return response


def update_dashboard(
    db: Session,
    dashboard_id: int,
    payload: DashboardUpdateRequest,
    current_user: AuthUser,
) -> DashboardDetailResponse:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    allowed_scope = _scope_for_role(current_user)
    current_visibility = _dashboard_actor_visibility(layout, allowed_scope)
    if not current_visibility:
        raise DashboardPermissionError("No permissions for this dashboard")

    if payload.name is not None:
        layout.name = payload.name.strip()
    if payload.description is not None:
        layout.description = payload.description.strip() or None
    if payload.widgets is not None:
        layout.layout_json = json.dumps([widget.model_dump() for widget in payload.widgets], separators=(",", ":"))

    if payload.allowed_store_ids is not None:
        requested_store_ids = _unique_ints(payload.allowed_store_ids)
        scoped_store_ids = _intersection(requested_store_ids, allowed_scope)
        if not scoped_store_ids:
            raise DashboardPermissionError("Dashboard must retain at least one permitted store")
        layout.allowed_store_ids_json = _as_json(scoped_store_ids)

    if payload.default_start_date is not None:
        layout.default_start_date = payload.default_start_date
    if payload.default_end_date is not None:
        layout.default_end_date = payload.default_end_date

    if layout.default_start_date and layout.default_end_date and layout.default_end_date < layout.default_start_date:
        raise ValueError("default_end_date must be on or after default_start_date")

    db.flush()
    audit_event(
        db,
        action="dashboard.updated",
        resource_type="dashboard",
        resource_id=str(layout.id),
        actor_user_id=current_user.id,
        detail={
            "name": layout.name,
            "allowed_store_ids": _dashboard_allowed_store_ids(layout),
        },
    )

    return get_dashboard_detail(
        db,
        layout.id,
        current_user=current_user,
        requested_store_ids=None,
        start_date=None,
        end_date=None,
    )


def delete_dashboard(db: Session, dashboard_id: int, current_user: AuthUser) -> None:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    actor_scope = _scope_for_role(current_user)
    if not _dashboard_actor_visibility(layout, actor_scope):
        raise DashboardPermissionError("No permissions for this dashboard")

    layout.is_archived = True
    db.flush()
    audit_event(
        db,
        action="dashboard.archived",
        resource_type="dashboard",
        resource_id=str(layout.id),
        actor_user_id=current_user.id,
        detail={"name": layout.name},
    )


def get_dashboard_detail(
    db: Session,
    dashboard_id: int,
    *,
    current_user: AuthUser,
    requested_store_ids: list[int] | None,
    start_date: date | None,
    end_date: date | None,
    read_only: bool = False,
) -> DashboardDetailResponse:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    actor_scope = _scope_for_role(current_user)
    dashboard_store_ids = _dashboard_allowed_store_ids(layout)
    scoped_store_ids = _scope_dashboard_store_ids(
        dashboard_store_ids=dashboard_store_ids,
        actor_scope_store_ids=actor_scope,
        requested_store_ids=requested_store_ids,
    )

    resolved_start, resolved_end = _resolve_window(
        requested_start=start_date,
        requested_end=end_date,
        default_start=layout.default_start_date,
        default_end=layout.default_end_date,
    )
    data = _build_data_payload(scoped_store_ids, resolved_start, resolved_end)

    return DashboardDetailResponse(
        id=layout.id,
        name=layout.name,
        description=layout.description,
        widgets=_layout_widgets(layout),
        allowed_store_ids=scoped_store_ids,
        default_start_date=layout.default_start_date,
        default_end_date=layout.default_end_date,
        store_options=_store_options(scoped_store_ids),
        read_only=read_only,
        data=data,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


def create_share_link(
    db: Session,
    dashboard_id: int,
    payload: ShareLinkCreateRequest,
    current_user: AuthUser,
    frontend_base_url: str,
) -> ShareLinkResponse:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    actor_scope = _scope_for_role(current_user)
    dashboard_store_ids = _dashboard_allowed_store_ids(layout)

    if not _dashboard_actor_visibility(layout, actor_scope):
        raise DashboardPermissionError("No permissions for this dashboard")

    requested_store_ids = payload.allowed_store_ids if payload.allowed_store_ids else None
    scoped_store_ids = _scope_dashboard_store_ids(
        dashboard_store_ids=dashboard_store_ids,
        actor_scope_store_ids=actor_scope,
        requested_store_ids=requested_store_ids,
    )

    token = token_urlsafe(30)
    link = DashboardShareLink(
        dashboard_id=layout.id,
        token=token,
        created_by_user_id=current_user.id,
        allowed_store_ids_json=_as_json(scoped_store_ids),
        start_date=payload.start_date,
        end_date=payload.end_date,
        readonly=True,
        is_active=True,
        expires_at=payload.expires_at,
    )
    db.add(link)
    db.flush()

    audit_event(
        db,
        action="dashboard.share_link.created",
        resource_type="dashboard_share_link",
        resource_id=str(link.id),
        actor_user_id=current_user.id,
        detail={
            "dashboard_id": layout.id,
            "allowed_store_ids": scoped_store_ids,
            "readonly": True,
        },
    )

    return ShareLinkResponse(
        id=link.id,
        dashboard_id=layout.id,
        token=link.token,
        share_url=f"{frontend_base_url.rstrip('/')}/shared/{link.token}",
        readonly=link.readonly,
        is_active=link.is_active,
        allowed_store_ids=scoped_store_ids,
        start_date=link.start_date,
        end_date=link.end_date,
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


def list_share_links(
    db: Session,
    dashboard_id: int,
    current_user: AuthUser,
    frontend_base_url: str,
) -> list[ShareLinkResponse]:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    actor_scope = _scope_for_role(current_user)
    if not _dashboard_actor_visibility(layout, actor_scope):
        raise DashboardPermissionError("No permissions for this dashboard")

    links = db.execute(
        select(DashboardShareLink)
        .where(DashboardShareLink.dashboard_id == dashboard_id)
        .order_by(DashboardShareLink.created_at.desc())
    ).scalars()

    responses: list[ShareLinkResponse] = []
    for link in links:
        responses.append(
            ShareLinkResponse(
                id=link.id,
                dashboard_id=link.dashboard_id,
                token=link.token,
                share_url=f"{frontend_base_url.rstrip('/')}/shared/{link.token}",
                readonly=link.readonly,
                is_active=link.is_active,
                allowed_store_ids=_from_json(link.allowed_store_ids_json),
                start_date=link.start_date,
                end_date=link.end_date,
                expires_at=link.expires_at,
                created_at=link.created_at,
            )
        )
    return responses


def deactivate_share_link(db: Session, dashboard_id: int, link_id: int, current_user: AuthUser) -> None:
    layout = _get_dashboard_or_raise(db, dashboard_id)
    actor_scope = _scope_for_role(current_user)
    if not _dashboard_actor_visibility(layout, actor_scope):
        raise DashboardPermissionError("No permissions for this dashboard")

    link = db.execute(
        select(DashboardShareLink).where(
            DashboardShareLink.id == link_id,
            DashboardShareLink.dashboard_id == dashboard_id,
        )
    ).scalar_one_or_none()
    if not link:
        raise SharedLinkNotFoundError("Share link not found")

    link.is_active = False
    db.flush()
    audit_event(
        db,
        action="dashboard.share_link.deactivated",
        resource_type="dashboard_share_link",
        resource_id=str(link.id),
        actor_user_id=current_user.id,
        detail={"dashboard_id": dashboard_id},
    )


def resolve_shared_dashboard(
    db: Session,
    token: str,
    *,
    requested_store_ids: list[int] | None,
    start_date: date | None,
    end_date: date | None,
) -> SharedDashboardResponse:
    now_utc = datetime.now(timezone.utc)
    link = db.execute(
        select(DashboardShareLink).where(
            DashboardShareLink.token == token,
            DashboardShareLink.readonly.is_(True),
        )
    ).scalar_one_or_none()

    if not link:
        raise SharedLinkNotFoundError("Share link not found")
    if not link.is_active:
        raise SharedLinkNotFoundError("Share link is inactive")
    if link.expires_at and _to_utc(link.expires_at) <= now_utc:
        raise SharedLinkNotFoundError("Share link has expired")

    layout = _get_dashboard_or_raise(db, link.dashboard_id)
    link_store_ids = _from_json(link.allowed_store_ids_json)
    dashboard_store_ids = _dashboard_allowed_store_ids(layout)
    scoped_store_ids = _intersection(link_store_ids, dashboard_store_ids)
    if requested_store_ids:
        scoped_store_ids = _intersection(scoped_store_ids, _unique_ints(requested_store_ids))
    if not scoped_store_ids:
        raise DashboardPermissionError("No permitted stores available for this share link")

    resolved_start, resolved_end = _resolve_window(
        requested_start=start_date,
        requested_end=end_date,
        default_start=link.start_date or layout.default_start_date,
        default_end=link.end_date or layout.default_end_date,
    )
    data = _build_data_payload(scoped_store_ids, resolved_start, resolved_end)

    audit_event(
        db,
        action="dashboard.share_link.accessed",
        resource_type="dashboard_share_link",
        resource_id=str(link.id),
        actor_user_id=None,
        detail={
            "dashboard_id": layout.id,
            "store_ids": scoped_store_ids,
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
        },
    )

    return SharedDashboardResponse(
        dashboard_id=layout.id,
        token=link.token,
        name=layout.name,
        description=layout.description,
        widgets=_layout_widgets(layout),
        allowed_store_ids=scoped_store_ids,
        store_options=_store_options(scoped_store_ids),
        read_only=True,
        data=data,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


def _csv_bytes(data: DashboardDataPayload) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["store_id", "store_name", "business_date", "orders", "revenue", "refunds", "cost", "gross_margin"])
    for row in data.rows:
        writer.writerow(
            [
                row.store_id,
                row.store_name,
                row.business_date.isoformat(),
                row.orders,
                f"{row.revenue:.2f}",
                f"{row.refunds:.2f}",
                f"{row.cost:.2f}",
                f"{row.gross_margin:.2f}",
            ]
        )
    return buffer.getvalue().encode("utf-8")


def _png_bytes(dashboard_name: str, data: DashboardDataPayload) -> bytes:
    width = 1100
    height = 620
    image = Image.new("RGB", (width, height), color=(245, 248, 252))
    draw = ImageDraw.Draw(image)

    draw.rectangle((24, 24, width - 24, height - 24), fill=(255, 255, 255), outline=(210, 220, 232), width=2)
    draw.text((48, 44), "MeridianOps Dashboard Export", fill=(18, 50, 87))
    draw.text((48, 78), f"Name: {dashboard_name}", fill=(32, 42, 58))
    draw.text((48, 104), f"Generated: {datetime.now(timezone.utc).isoformat()}", fill=(64, 72, 88))

    draw.text((48, 152), f"Orders: {data.totals.orders}", fill=(20, 35, 70))
    draw.text((48, 176), f"Revenue: {data.totals.revenue:.2f}", fill=(20, 35, 70))
    draw.text((48, 200), f"Refunds: {data.totals.refunds:.2f}", fill=(20, 35, 70))
    draw.text((48, 224), f"Gross Margin: {data.totals.gross_margin:.2f}", fill=(20, 35, 70))

    table_top = 272
    draw.text((48, table_top), "Store", fill=(18, 50, 87))
    draw.text((280, table_top), "Orders", fill=(18, 50, 87))
    draw.text((420, table_top), "Revenue", fill=(18, 50, 87))
    draw.text((600, table_top), "Margin", fill=(18, 50, 87))

    y = table_top + 24
    for row in data.by_store[:12]:
        draw.text((48, y), row.store_name, fill=(35, 45, 65))
        draw.text((280, y), str(row.orders), fill=(35, 45, 65))
        draw.text((420, y), f"{row.revenue:.2f}", fill=(35, 45, 65))
        draw.text((600, y), f"{row.gross_margin:.2f}", fill=(35, 45, 65))
        y += 24

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _pdf_bytes(dashboard_name: str, data: DashboardDataPayload) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    pdf.setTitle(f"MeridianOps Dashboard - {dashboard_name}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, height - 48, "MeridianOps Dashboard Export")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(48, height - 74, f"Name: {dashboard_name}")
    pdf.drawString(48, height - 92, f"Generated: {datetime.now(timezone.utc).isoformat()}")

    pdf.drawString(48, height - 126, f"Orders: {data.totals.orders}")
    pdf.drawString(190, height - 126, f"Revenue: {data.totals.revenue:.2f}")
    pdf.drawString(360, height - 126, f"Margin: {data.totals.gross_margin:.2f}")

    y = height - 164
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, y, "Store")
    pdf.drawString(240, y, "Orders")
    pdf.drawString(320, y, "Revenue")
    pdf.drawString(430, y, "Margin")
    y -= 18

    pdf.setFont("Helvetica", 10)
    for row in data.by_store[:24]:
        if y < 60:
            pdf.showPage()
            y = height - 54
            pdf.setFont("Helvetica", 10)
        pdf.drawString(48, y, row.store_name)
        pdf.drawRightString(295, y, str(row.orders))
        pdf.drawRightString(405, y, f"{row.revenue:.2f}")
        pdf.drawRightString(540, y, f"{row.gross_margin:.2f}")
        y -= 16

    pdf.save()
    return buffer.getvalue()


def export_dashboard(
    *,
    format_name: str,
    dashboard_name: str,
    data: DashboardDataPayload,
) -> tuple[str, str, bytes]:
    normalized = format_name.strip().lower()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    if normalized == "csv":
        filename = f"dashboard-{timestamp}.csv"
        payload = _csv_bytes(data)
        logger.info(
            "dashboard_export_generated",
            extra={"format": "csv", "dashboard_name": dashboard_name, "size_bytes": len(payload)},
        )
        return filename, "text/csv; charset=utf-8", payload
    if normalized == "png":
        filename = f"dashboard-{timestamp}.png"
        payload = _png_bytes(dashboard_name, data)
        logger.info(
            "dashboard_export_generated",
            extra={"format": "png", "dashboard_name": dashboard_name, "size_bytes": len(payload)},
        )
        return filename, "image/png", payload
    if normalized == "pdf":
        filename = f"dashboard-{timestamp}.pdf"
        payload = _pdf_bytes(dashboard_name, data)
        logger.info(
            "dashboard_export_generated",
            extra={"format": "pdf", "dashboard_name": dashboard_name, "size_bytes": len(payload)},
        )
        return filename, "application/pdf", payload

    raise ExportError("Unsupported export format")


def record_export_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    dashboard_id: int,
    format_name: str,
    file_size: int,
    shared_token: str | None = None,
) -> None:
    audit_event(
        db,
        action="dashboard.exported",
        resource_type="dashboard",
        resource_id=str(dashboard_id),
        actor_user_id=actor_user_id,
        detail={
            "format": format_name,
            "file_size": file_size,
            "shared_token": shared_token,
        },
    )


def get_dashboard_audit_rows(db: Session, dashboard_id: int, current_user: AuthUser) -> list[AuditLog]:
    _scope_for_role(current_user)
    _get_dashboard_or_raise(db, dashboard_id)

    share_link_ids = [
        str(link_id)
        for link_id in db.execute(
            select(DashboardShareLink.id).where(DashboardShareLink.dashboard_id == dashboard_id)
        ).scalars()
    ]

    share_link_filter = (
        and_(
            AuditLog.resource_type == "dashboard_share_link",
            AuditLog.resource_id.in_(share_link_ids),
        )
        if share_link_ids
        else AuditLog.id == -1
    )

    rows = db.execute(
        select(AuditLog)
        .where(
            or_(
                and_(AuditLog.resource_type == "dashboard", AuditLog.resource_id == str(dashboard_id)),
                share_link_filter,
            )
        )
        .order_by(AuditLog.id.desc())
        .limit(200)
    ).scalars()
    return list(rows)
