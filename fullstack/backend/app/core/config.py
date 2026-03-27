from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "MeridianOps Retail Performance API"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meridianops"
    backend_cors_origins: str = "http://localhost:5173"
    auth_min_password_length: int = 12
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    auth_session_minutes: int = 720
    field_encryption_key: str | None = None
    scheduler_enabled: bool = True
    scheduler_kpi_hour_utc: int = 2
    scheduler_start_on_boot: bool = False

    @property
    def backend_cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def auth_cookie_secure(self) -> bool:
        # Keep local/dev/test ergonomics while requiring secure cookies elsewhere.
        return self.app_env.strip().lower() not in {"local", "dev", "development", "test"}


settings = Settings()
