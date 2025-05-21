import inject
import pytest
from pytest_mock import MockerFixture

from app.bindings import get_config
from app.config.models import AppConfig


def test_get_config_returns_bound_config(mocker: MockerFixture) -> None:
    bound_config = mocker.Mock(spec=AppConfig)
    mocker.patch("inject.instance", return_value=bound_config)
    config = get_config()

    assert config == bound_config
