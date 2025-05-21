from fastapi import FastAPI
from inject import Binder
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_mock import MockerFixture

from app.config.models import AppConfig, TelemetryConfig
from app.main import create_app
from app.telemetry.jaeger_provider import setup_jaeger
from tests.utils import clear_bindings, configure_bindings, load_app_config


def test_setup_jaeger_calls_instrument_app_with_correct_params(
    mocker: MockerFixture,
) -> None:
    app_config = load_app_config()
    app_config.telemetry.enabled = True

    def overrides(binder: Binder) -> Binder:
        binder.bind(TelemetryConfig, app_config.telemetry)
        binder.bind(SpanExporter, InMemorySpanExporter())

        return binder

    configure_bindings(bindings_override=overrides)
    app = create_app()
    mocker.patch("opentelemetry.trace.set_tracer_provider")

    mock_instrument_app = mocker.patch(
        "app.telemetry.jaeger_provider.FastAPIInstrumentor.instrument_app"
    )

    setup_jaeger(app)
    mock_instrument_app.assert_called_once()
    called_args, called_kwargs = mock_instrument_app.call_args
    assert called_args[0] == app
    assert called_kwargs["exclude_spans"] == ["receive", "send"]
    assert "tracer_provider" in called_kwargs
    clear_bindings()


def test_setup_jaeger_does_not_call_instrument_app_when_disabled(
    mocker: MockerFixture,
    test_client: FastAPI,
) -> None:
    mock_instrument_app = mocker.patch(
        "app.telemetry.jaeger_provider.FastAPIInstrumentor.instrument_app"
    )

    setup_jaeger(test_client)

    mock_instrument_app.assert_not_called()
    clear_bindings()
