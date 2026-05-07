from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
