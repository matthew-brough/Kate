from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


def broker_url_with_redis_password(broker_url: str, redis_password: str | None) -> str:
    if not redis_password:
        return broker_url

    parts = urlsplit(broker_url)
    if parts.scheme not in {"redis", "rediss"} or "@" in parts.netloc:
        return broker_url

    netloc = f":{quote(redis_password, safe='')}@{parts.netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "report-api"
    service_version: str = "0.1.0"
    env: str = "local"
    log_level: str = "INFO"

    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_enabled: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://reports:reports@localhost:5432/reports"
    )

    celery_broker_url: str = "redis://localhost:6379/0"
    redis_password: str | None = None

    @property
    def effective_celery_broker_url(self) -> str:
        return broker_url_with_redis_password(
            self.celery_broker_url,
            self.redis_password,
        )


settings = Settings()
