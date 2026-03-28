import json
from decimal import Decimal

from app.core.masking import mask_record
from app.db.models import AuditLog

SENSITIVE_AUDIT_KEYS = {
    "member_code",
    "coupon_code",
    "session_token",
    "qr_token",
    "nfc_tag",
    "device_id",
    "wallet_reference",
    "share_token",
    "shared_token",
    "email",
    "phone",
}


def audit_event(
    db,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_user_id: int | None,
    detail: dict,
) -> AuditLog:
    sanitized = {}
    for key, value in detail.items():
        if isinstance(value, Decimal):
            sanitized[key] = str(value)
        else:
            sanitized[key] = value
    masked = mask_record(sanitized, SENSITIVE_AUDIT_KEYS)

    entry = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_user_id=actor_user_id,
        detail_json=json.dumps(masked, sort_keys=True),
    )
    db.add(entry)
    return entry
