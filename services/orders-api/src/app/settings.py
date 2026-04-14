from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "orders-api"
    service_version: str = "0.1.0"
    env: str = "local"
    log_level: str = "INFO"

    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_enabled: bool = True

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://orders:orders@localhost:5432/orders"
    )


settings = Settings()
