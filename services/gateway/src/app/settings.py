from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def redis_url_with_password(redis_url: str, redis_password: str | None) -> str:
    if not redis_password:
        return redis_url

    parts = urlsplit(redis_url)
    if parts.scheme not in {"redis", "rediss"} or "@" in parts.netloc:
        return redis_url

    netloc = f":{quote(redis_password, safe='')}@{parts.netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "gateway"
    service_version: str = "0.1.0"
    env: str = "local"
    log_level: str = "INFO"

    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_enabled: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    # Upstream service base URLs (in-cluster)
    auth_api_url: str = "http://auth-api:8000"
    orders_api_url: str = "http://orders-api:8000"
    report_api_url: str = "http://report-api:8000"

    # Must match auth-api's jwt_secret, jwt_issuer, jwt_audience.
    # No usable default — empty value triggers min_length=1 on validate_default,
    # so a missing APP_JWT_SECRET fails at Settings() construction.
    jwt_secret: str = Field(default="", min_length=1, validate_default=True)
    jwt_issuer: str = "kate-auth-api"
    jwt_audience: str = "kate-platform"

    http_timeout: float = 30.0
    readiness_timeout: float = 2.0

    rate_limit_redis_url: str = "redis://localhost:6379/0"
    rate_limit_trust_x_forwarded_for: bool = False
    rate_limit_auth_token_requests: int = 10
    rate_limit_auth_token_window_seconds: int = 60
    rate_limit_auth_register_requests: int = 5
    rate_limit_auth_register_window_seconds: int = 60
    redis_password: str | None = None

    @property
    def effective_rate_limit_redis_url(self) -> str:
        return redis_url_with_password(
            self.rate_limit_redis_url,
            self.redis_password,
        )


settings = Settings()
