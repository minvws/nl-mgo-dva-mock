import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockFixture

from app.config.models import TelemetryConfig
from app.health.services import HealthChecker, HealthService, TelemetryHealthChecker
from tests.utils import configure_bindings


def test_health_endpoint_returns_200_when_healthy(test_client: TestClient) -> None:
    class AlwaysTrueHealthChecker(HealthChecker):
        name: str = "always_true_checker"

        def enabled(self) -> bool:
            return True

        def check(self) -> bool:
            return True

    static_health_service = HealthService(
        checkers=[AlwaysTrueHealthChecker()],
    )

    configure_bindings(
        bindings_override=lambda binder: binder.bind(
            HealthService, static_health_service
        )
    )

    response = test_client.get("/health")

    assert response.status_code == 200
    json = response.json()
    assert json["healthy"] is True
    assert "externals" in json
    assert "always_true_checker" in json["externals"]
    assert json["externals"]["always_true_checker"] is True


def test_health_endpoint_returns_503_when_unhealthy(test_client: TestClient) -> None:
    class FailingHealthChecker(HealthChecker):
        name: str = "failing_checker"

        def enabled(self) -> bool:
            return True

        def check(self) -> bool:
            return False

    configure_bindings(
        bindings_override=lambda binder: binder.bind(
            HealthService,
            HealthService(
                checkers=[FailingHealthChecker()],
            ),
        )
    )

    response = test_client.get("/health")

    assert response.status_code == 503
    json = response.json()
    assert json["healthy"] is False
    assert "externals" in json
    assert "failing_checker" in json["externals"]
    assert json["externals"]["failing_checker"] is False
