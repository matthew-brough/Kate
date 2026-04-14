from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "template-service"
    service_version: str = "0.1.0"
    env: str = "local"
    log_level: str = "INFO"

    # OTel collector gRPC endpoint
    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_enabled: bool = True

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
