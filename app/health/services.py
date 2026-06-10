import socket
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from app.config.models import TelemetryConfig
from app.health.models import HealthResponse


class HealthChecker(ABC):
    name: str

    def enabled(self) -> bool:
        return True

    @abstractmethod
    def check(self) -> bool: ...


class TelemetryHealthChecker(HealthChecker):
    def __init__(
        self,
        telemetry_config: TelemetryConfig,
    ) -> None:
        self.name = "telemetry"
        self._telemetry_config = telemetry_config

    def enabled(self) -> bool:
        return self._telemetry_config.enabled

    def check_telemetry_connectivity(
        self, collector_url: str, timeout: float = 1.0
    ) -> bool:
        parsed = urlparse(collector_url)
        host = parsed.hostname
        port = parsed.port or 4317  # Default OTLP gRPC port

        if not host:
            return False

        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def check(self) -> bool:
        return self.check_telemetry_connectivity(
            self._telemetry_config.collector_grpc_url
        )


class HealthService:
    def __init__(self, checkers: list[HealthChecker]) -> None:
        self._checkers = checkers

    def get_health(self) -> HealthResponse:
        externals: dict[str, bool] = {}
        results: list[bool] = []

        for checker in self._checkers:
            if not checker.enabled():
                continue

            status = checker.check()
            externals[checker.name] = status
            results.append(status)

        is_healthy = all(results) if results else True
        return HealthResponse(healthy=is_healthy, externals=externals)
