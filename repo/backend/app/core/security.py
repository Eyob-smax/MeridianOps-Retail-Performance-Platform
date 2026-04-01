from datetime import datetime, timedelta, timezone
import base64
import binascii
import hashlib
import hmac
import os

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

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ROUNDS = 240_000
_PBKDF2_ALLOWED_ENVS = {"local", "dev", "development", "test"}


def _pbkdf2_hash(raw_password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PBKDF2_PREFIX}${salt_b64}${digest_b64}"


def _pbkdf2_verify(raw_password: str, encoded: str) -> bool:
    try:
        _prefix, salt_b64, digest_b64 = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
    except (ValueError, binascii.Error):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return hmac.compare_digest(candidate, expected)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def password_is_valid(raw_password: str) -> bool:
    return len(raw_password) >= settings.auth_min_password_length


def bcrypt_required() -> bool:
    return settings.app_env.strip().lower() not in _PBKDF2_ALLOWED_ENVS


def assert_password_hashing_backend_ready() -> None:
    if bcrypt_required() and _bcrypt is None:
        raise RuntimeError("bcrypt dependency is required when app_env is not local/dev/test")


def hash_password(raw_password: str) -> str:
    if _bcrypt is not None:
        return _bcrypt.hashpw(raw_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    if bcrypt_required():
        raise RuntimeError("bcrypt dependency is required when app_env is not local/dev/test")
    return _pbkdf2_hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(f"{PBKDF2_PREFIX}$"):
        return _pbkdf2_verify(raw_password, hashed_password)
    if _bcrypt is None:
        return False
    return _bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))


def lockout_window_expires(minutes: int | None = None) -> datetime:
    lockout_minutes = minutes or settings.auth_lockout_minutes
    return utcnow() + timedelta(minutes=lockout_minutes)


def session_expires(minutes: int | None = None) -> datetime:
    ttl_minutes = minutes or settings.auth_session_minutes
    return utcnow() + timedelta(minutes=ttl_minutes)
