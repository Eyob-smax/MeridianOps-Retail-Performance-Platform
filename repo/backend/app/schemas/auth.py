from pydantic import BaseModel, Field

from app.types.roles import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuthUser(BaseModel):
    id: int
    store_id: int | None = None
    username: str
    display_name: str
    roles: list[UserRole]


class LoginResponse(BaseModel):
    message: str
    user: AuthUser


class SessionResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None


class LogoutResponse(BaseModel):
    message: str
