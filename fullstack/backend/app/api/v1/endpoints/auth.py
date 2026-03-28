from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps.auth import SESSION_COOKIE_NAME, get_current_user, require_roles
from app.core.config import settings
from app.core.errors import bad_request, unauthorized
from app.db.session import get_db
from app.schemas.auth import AuthUser, LoginRequest, LoginResponse, LogoutResponse, SessionResponse
from app.schemas.security import SecurityPolicyResponse
from app.services.auth_service import (
    authenticate_user,
    get_user_with_roles,
    issue_session,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if len(payload.password) < settings.auth_min_password_length:
        raise bad_request(
            f"Password must be at least {settings.auth_min_password_length} characters."
        )

    user, error_code, locked_until = authenticate_user(db, payload.username, payload.password)

    if error_code == "locked":
        db.commit()
        detail = "Account is temporarily locked due to repeated failed attempts."
        if locked_until:
            detail = f"Account locked until {locked_until}."
        raise unauthorized(detail)

    if error_code:
        db.commit()
        raise unauthorized("Invalid username or password")

    assert user is not None
    session = issue_session(db, user.id)
    hydrated = get_user_with_roles(db, user.id)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_minutes * 60,
        path="/",
    )

    roles = hydrated[1] if hydrated else []
    user_data = AuthUser(
        id=user.id,
        store_id=user.store_id,
        username=user.username,
        display_name=user.display_name,
        roles=roles,
    )
    return LoginResponse(message="Login successful", user=user_data)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> LogoutResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        revoke_session(db, token)
        db.commit()

    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return LogoutResponse(message="Logged out")


@router.get("/session", response_model=SessionResponse)
def validate_session(current_user: AuthUser = Depends(get_current_user)) -> SessionResponse:
    return SessionResponse(authenticated=True, user=current_user)


@router.get("/security-policy", response_model=SecurityPolicyResponse)
def security_policy(
    _: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
) -> SecurityPolicyResponse:
    return SecurityPolicyResponse(
        min_password_length=settings.auth_min_password_length,
        max_failed_attempts=settings.auth_max_failed_attempts,
        lockout_minutes=settings.auth_lockout_minutes,
        session_minutes=settings.auth_session_minutes,
        masking_enabled_default=True,
        encryption_enabled=bool(settings.field_encryption_key),
    )
