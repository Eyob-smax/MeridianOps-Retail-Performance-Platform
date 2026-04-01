from pydantic import BaseModel


class APIError(BaseModel):
    code: str
    message: str
    detail: str | None = None
