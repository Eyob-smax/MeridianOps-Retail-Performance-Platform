from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str = Field(description="Service health status")
    detail: str = Field(description="Additional status details")


class AppHealthResponse(BaseModel):
    name: str
    environment: str
    version: str
    api_status: HealthCheck
    database_status: HealthCheck | None = None
