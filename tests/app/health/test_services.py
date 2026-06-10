from pytest_mock import MockerFixture

from app.config.models import TelemetryConfig
from app.health.services import HealthChecker, HealthService, TelemetryHealthChecker


class TestHealthService:
    def test_get_health_with_all_checkers_healthy_returns_true(self) -> None:
        class PassingChecker(HealthChecker):
            name: str = "pass"

            def check(self) -> bool:
                return True

        service = HealthService(checkers=[PassingChecker()])
        health_response = service.get_health()

        assert health_response.healthy is True
        assert health_response.externals["pass"] is True

    def test_get_health_with_disabled_checker_excludes_from_response(self) -> None:
        service = HealthService(
            checkers=[
                TelemetryHealthChecker(
                    TelemetryConfig(
                        enabled=False,
                        service_name="Mock",
                        collector_grpc_url="http://localhost:4317",
                    )
                )
            ]
        )

        health_response = service.get_health()

        assert health_response.healthy is True
        assert "telemetry" not in health_response.externals

    def test_get_health_with_failing_checker_returns_unhealthy(self) -> None:
        class FailingChecker(HealthChecker):
            name: str = "fail"

            def check(self) -> bool:
                return False

        service = HealthService(checkers=[FailingChecker()])
        health_response = service.get_health()

        assert health_response.healthy is False
        assert health_response.externals["fail"] is False

    def test_get_health_with_multiple_checkers_all_healthy(self) -> None:
        class Checker1(HealthChecker):
            name: str = "check1"

            def check(self) -> bool:
                return True

        class Checker2(HealthChecker):
            name: str = "check2"

            def check(self) -> bool:
                return True

        service = HealthService(checkers=[Checker1(), Checker2()])
        health_response = service.get_health()

        assert health_response.healthy is True
        assert health_response.externals == {"check1": True, "check2": True}

    def test_get_health_with_no_checkers_returns_healthy(self) -> None:
        service = HealthService(checkers=[])
        health_response = service.get_health()

        assert health_response.healthy is True
        assert health_response.externals == {}


class TestTelemetryHealthChecker:
    def test_check_telemetry_connectivity_with_missing_hostname_returns_false(
        self,
    ) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)

        result = checker.check_telemetry_connectivity("http://")

        assert result is False

    def test_check_telemetry_connectivity_with_connection_error_returns_false(
        self,
        mocker: MockerFixture,
    ) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)
        mocker.patch(
            "app.health.services.socket.create_connection",
            side_effect=OSError("Connection refused"),
        )

        result = checker.check_telemetry_connectivity("http://localhost:4317")

        assert result is False

    def test_check_telemetry_connectivity_with_successful_connection_returns_true(
        self,
        mocker: MockerFixture,
    ) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)
        mock_socket = mocker.MagicMock()
        mocker.patch(
            "app.health.services.socket.create_connection",
            return_value=mock_socket.__enter__.return_value,
        )

        result = checker.check_telemetry_connectivity("http://localhost:4317")

        assert result is True

    def test_check_with_enabled_telemetry_returns_true(
        self,
        mocker: MockerFixture,
    ) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)
        mock_socket = mocker.MagicMock()
        mocker.patch(
            "app.health.services.socket.create_connection",
            return_value=mock_socket.__enter__.return_value,
        )

        result = checker.check()

        assert result is True

    def test_enabled_returns_true_when_telemetry_is_enabled(self) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)

        result = checker.enabled()

        assert result is True

    def test_enabled_returns_false_when_telemetry_is_disabled(self) -> None:
        telemetry_config = TelemetryConfig(
            enabled=False,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)

        result = checker.enabled()

        assert result is False

    def test_check_with_enabled_telemetry_and_failed_connection_returns_false(
        self,
        mocker: MockerFixture,
    ) -> None:
        telemetry_config = TelemetryConfig(
            enabled=True,
            service_name="Mock",
            collector_grpc_url="http://localhost:4317",
        )
        checker = TelemetryHealthChecker(telemetry_config)
        mocker.patch(
            "app.health.services.socket.create_connection",
            side_effect=OSError("Connection refused"),
        )

        result = checker.check()

        assert result is False


def test_health_checker_enabled_default_returns_true() -> None:
    class TestHealthChecker(HealthChecker):
        def __init__(self) -> None:
            self.name = "test"

        def check(self) -> bool:
            return True

    checker = TestHealthChecker()

    result = checker.enabled()

    assert result is True
