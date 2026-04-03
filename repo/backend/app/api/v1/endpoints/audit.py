from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import require_roles
from app.db.models import AuditLog
from app.db.session import get_db
from app.schemas.auth import AuthUser

router = APIRouter(prefix="/audit", tags=["audit"])

_AUDIT_ROLES = {"administrator", "store_manager"}


class AuditEntryResponse:
    pass


@router.get("/events")
def list_audit_events(
    resource_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthUser = Depends(require_roles(_AUDIT_ROLES)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Query audit trail with optional filters by resource_type and action.

    Supports filtering for loyalty, campaign, order, inventory, and other operational events.
    """
    stmt = select(AuditLog).order_by(AuditLog.id.desc())

    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))

    stmt = stmt.limit(limit)
    entries = db.execute(stmt).scalars().all()

    return [
        {
            "id": entry.id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "actor_user_id": entry.actor_user_id,
            "detail_json": entry.detail_json,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]


@router.get("/events/member")
def list_member_audit_events(
    member_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthUser = Depends(require_roles(_AUDIT_ROLES)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Query audit trail for member/loyalty/wallet operations."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.resource_type == "member")
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    entries = db.execute(stmt).scalars().all()

    results = []
    for entry in entries:
        if member_code:
            # Filter by member_code in detail_json (masked, so partial match)
            if member_code.upper() not in (entry.detail_json or "").upper():
                continue
        results.append({
            "id": entry.id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "actor_user_id": entry.actor_user_id,
            "detail_json": entry.detail_json,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        })
    return results


@router.get("/events/campaign")
def list_campaign_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthUser = Depends(require_roles(_AUDIT_ROLES)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Query audit trail for campaign/coupon operations."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.action.like("campaign%") | AuditLog.action.like("coupon%"))
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    entries = db.execute(stmt).scalars().all()

    return [
        {
            "id": entry.id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "actor_user_id": entry.actor_user_id,
            "detail_json": entry.detail_json,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]


@router.get("/events/order")
def list_order_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthUser = Depends(require_roles(_AUDIT_ROLES)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Query audit trail for order lifecycle operations."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.resource_type == "order")
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    entries = db.execute(stmt).scalars().all()

    return [
        {
            "id": entry.id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "actor_user_id": entry.actor_user_id,
            "detail_json": entry.detail_json,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]
