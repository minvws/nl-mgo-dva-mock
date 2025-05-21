from pydantic import BaseModel, Field


class InjectableConfig(BaseModel):
    pass


class LoggingConfig(InjectableConfig):
    logger_name: str = "app"
    log_level: str = "DEBUG"


class TelemetryConfig(InjectableConfig):
    enabled: bool = True
    service_name: str = "Proxy"
    collector_grpc_url: str = "http://jaeger:4317"


class OAuthConfig(BaseModel):
    # Enable/disable mocked oauth servers (auth, token)
    mock_oauth_servers: bool = False


class AppConfig(BaseModel):
    base_url: str = "http://localhost:8000"
    use_demo_hcims: bool = False
    telemetry: TelemetryConfig
    logging: LoggingConfig = LoggingConfig()
    oauth: OAuthConfig
