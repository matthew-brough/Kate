from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "worker"
    service_version: str = "0.1.0"
    env: str = "local"
    log_level: str = "INFO"

    # Same DB as report-api — worker writes results to the reports table.
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://reports:reports@localhost:5432/reports"
    )

    celery_broker_url: str = "redis://localhost:6379/0"


settings = Settings()
