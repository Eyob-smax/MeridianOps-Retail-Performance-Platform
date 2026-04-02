from datetime import datetime, timedelta, timezone

try:
    import bcrypt as _bcrypt
except ModuleNotFoundError:
    _bcrypt = None

from app.core.config import settings

ROLE_ADMINISTRATOR = "administrator"
ROLE_STORE_MANAGER = "store_manager"
ROLE_INVENTORY_CLERK = "inventory_clerk"
ROLE_CASHIER = "cashier"
ROLE_EMPLOYEE = "employee"

ALL_ROLES = {
    ROLE_ADMINISTRATOR,
    ROLE_STORE_MANAGER,
    ROLE_INVENTORY_CLERK,
    ROLE_CASHIER,
    ROLE_EMPLOYEE,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def password_is_valid(raw_password: str) -> bool:
    return len(raw_password) >= settings.auth_min_password_length


def assert_password_hashing_backend_ready() -> None:
    if _bcrypt is None:
        raise RuntimeError("bcrypt dependency is required for password hashing")


def hash_password(raw_password: str) -> str:
    assert_password_hashing_backend_ready()
    return _bcrypt.hashpw(raw_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    if _bcrypt is None:
        return False
    try:
        return _bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def lockout_window_expires(minutes: int | None = None) -> datetime:
    lockout_minutes = minutes or settings.auth_lockout_minutes
    return utcnow() + timedelta(minutes=lockout_minutes)


def session_expires(minutes: int | None = None) -> datetime:
    ttl_minutes = minutes or settings.auth_session_minutes
    return utcnow() + timedelta(minutes=ttl_minutes)
