from datetime import timedelta
from secrets import token_hex

from sqlalchemy import and_, delete, desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    ALL_ROLES,
    hash_password,
    lockout_window_expires,
    password_is_valid,
    session_expires,
    utcnow,
    verify_password,
)
from app.db.models import AuthAttempt, LockoutWindow, User, UserRole, UserSession
from app.utils.datetime import to_utc

DEFAULT_LOCAL_USERS: tuple[tuple[str, str, str], ...] = (
    ("admin", "Local Administrator", "administrator"),
    ("manager", "Store Manager", "store_manager"),
    ("clerk", "Inventory Clerk", "inventory_clerk"),
    ("cashier", "Cashier", "cashier"),
    ("employee", "Employee", "employee"),
)
DEFAULT_PASSWORD = "ChangeMeNow123"


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _fetch_lockout(db: Session, username: str) -> LockoutWindow | None:
    stmt = select(LockoutWindow).where(LockoutWindow.username == username)
    return db.execute(stmt).scalar_one_or_none()


def _is_active_lockout(lockout: LockoutWindow | None) -> bool:
    return bool(lockout and to_utc(lockout.locked_until) > utcnow())


def _get_recent_failed_attempts(db: Session, username: str) -> list[AuthAttempt]:
    cutoff = utcnow()
    stmt = (
        select(AuthAttempt)
        .where(
            and_(
                AuthAttempt.username == username,
                AuthAttempt.success.is_(False),
                AuthAttempt.attempted_at >= cutoff - timedelta(minutes=settings.auth_lockout_minutes),
            )
        )
        .order_by(desc(AuthAttempt.attempted_at))
    )
    return list(db.execute(stmt).scalars().all())


def _record_attempt(db: Session, username: str, success: bool, failure_reason: str | None = None) -> None:
    db.add(AuthAttempt(username=username, success=success, failure_reason=failure_reason))


def _apply_lockout_if_needed(db: Session, username: str) -> LockoutWindow | None:
    recent_failures = _get_recent_failed_attempts(db, username)
    if len(recent_failures) < settings.auth_max_failed_attempts:
        return None

    lockout = _fetch_lockout(db, username)
    new_expiration = lockout_window_expires()
    if lockout:
        lockout.locked_until = new_expiration
        return lockout

    lockout = LockoutWindow(username=username, locked_until=new_expiration)
    db.add(lockout)
    return lockout


def create_user(
    db: Session,
    username: str,
    password: str,
    display_name: str,
    roles: list[str],
) -> User:
    normalized = _normalize_username(username)
    if not password_is_valid(password):
        raise ValueError(f"Password must be at least {settings.auth_min_password_length} characters.")
    if not roles:
        raise ValueError("At least one role is required.")
    for role in roles:
        if role not in ALL_ROLES:
            raise ValueError(f"Unsupported role: {role}")

    existing = db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()
    if existing:
        raise ValueError("Username already exists")

    user = User(
        username=normalized,
        password_hash=hash_password(password),
        display_name=display_name,
        is_active=True,
    )
    db.add(user)
    db.flush()

    for role in sorted(set(roles)):
        db.add(UserRole(user_id=user.id, role_name=role))

    return user


def ensure_seed_users(db: Session) -> None:
    for username, display_name, role in DEFAULT_LOCAL_USERS:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            continue
        create_user(
            db=db,
            username=username,
            password=DEFAULT_PASSWORD,
            display_name=display_name,
            roles=[role],
        )


def authenticate_user(db: Session, username: str, password: str) -> tuple[User | None, str | None, str | None]:
    normalized = _normalize_username(username)
    lockout = _fetch_lockout(db, normalized)
    if _is_active_lockout(lockout):
        _record_attempt(db, normalized, success=False, failure_reason="locked")
        locked_until = to_utc(lockout.locked_until).isoformat() if lockout else None
        return None, "locked", locked_until

    stmt = select(User).where(User.username == normalized, User.is_active.is_(True))
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        _record_attempt(db, normalized, success=False, failure_reason="invalid_credentials")
        db.flush()
        applied = _apply_lockout_if_needed(db, normalized)
        if applied:
            return None, "locked", to_utc(applied.locked_until).isoformat()
        return None, "invalid_credentials", None

    _record_attempt(db, normalized, success=True)
    if lockout:
        db.delete(lockout)
    return user, None, None


def issue_session(db: Session, user_id: int) -> UserSession:
    session = UserSession(session_token=token_hex(32), user_id=user_id, expires_at=session_expires())
    db.add(session)
    db.flush()
    return session


def revoke_session(db: Session, session_token: str) -> bool:
    stmt = select(UserSession).where(UserSession.session_token == session_token)
    session = db.execute(stmt).scalar_one_or_none()
    if not session or session.revoked_at is not None:
        return False
    session.revoked_at = utcnow()
    return True


def get_active_session(db: Session, session_token: str) -> UserSession | None:
    stmt = select(UserSession).where(
        UserSession.session_token == session_token,
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > utcnow(),
    )
    return db.execute(stmt).scalar_one_or_none()


def get_user_with_roles(db: Session, user_id: int) -> tuple[User, list[str]] | None:
    user = db.execute(select(User).where(User.id == user_id, User.is_active.is_(True))).scalar_one_or_none()
    if not user:
        return None
    roles = list(db.execute(select(UserRole.role_name).where(UserRole.user_id == user_id)).scalars().all())
    return user, roles


def validate_new_password(password: str) -> bool:
    return password_is_valid(password)


def cleanup_expired_sessions(db: Session) -> None:
    db.execute(delete(UserSession).where(UserSession.expires_at <= utcnow()))
