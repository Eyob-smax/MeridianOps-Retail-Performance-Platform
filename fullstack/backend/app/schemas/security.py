from pydantic import BaseModel


class SecurityPolicyResponse(BaseModel):
    min_password_length: int
    max_failed_attempts: int
    lockout_minutes: int
    session_minutes: int
    masking_enabled_default: bool
    encryption_enabled: bool
