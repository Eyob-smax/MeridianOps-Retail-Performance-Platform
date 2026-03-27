from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import forbidden, unauthorized
from app.db.session import get_db
from app.schemas.auth import AuthUser
from app.services.auth_service import get_active_session, get_user_with_roles

SESSION_COOKIE_NAME = "meridianops_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise unauthorized()

    session = get_active_session(db, session_token)
    if not session:
        raise unauthorized("Session expired or invalid")

    payload = get_user_with_roles(db, session.user_id)
    if not payload:
        raise unauthorized("User is inactive")

    user, roles = payload
    return AuthUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=roles,
    )


def require_roles(allowed_roles: set[str]):
    def _require(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not any(role in allowed_roles for role in current_user.roles):
            raise forbidden()
        return current_user

    return _require


def require_administrator(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if "administrator" not in current_user.roles:
        raise forbidden()
    return current_user


def require_store_manager(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not any(role in {"administrator", "store_manager"} for role in current_user.roles):
        raise forbidden()
    return current_user


def require_inventory_clerk(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not any(role in {"administrator", "inventory_clerk"} for role in current_user.roles):
        raise forbidden()
    return current_user


def require_cashier(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not any(role in {"administrator", "cashier"} for role in current_user.roles):
        raise forbidden()
    return current_user


def require_employee(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not any(role in {"administrator", "employee"} for role in current_user.roles):
        raise forbidden()
    return current_user
