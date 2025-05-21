from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterGRPC,
)
import configparser
import logging
import logging.config

import inject
from inject import Binder

from app.config.models import AppConfig, InjectableConfig
from app.config.services import ConfigParser
from app.hcim.matchers import HCIMResourceMatcher
from app.path import project_root, resource_dir
from app.utils import root_path
from app.version.models import VersionInfo
from app.version.services import read_version_info
from fhir.scanner import ResourceScanner


def configure_bindings(binder: Binder, config_file: str) -> None:
    """
    Configure dependency bindings for the application.
    """
    app_config: AppConfig = __parse_app_config(config_file=config_file)
    binder.bind(AppConfig, app_config)

    logger = __bind_logger(binder, app_config)
    __bind_sub_configs(binder, app_config, logger)
    __bind_resource_scanner(binder)
    __bind_hcim_resource_matcher(binder)
    __bind_span_processor(binder, app_config)
    binder.bind(VersionInfo, read_version_info())


def __parse_app_config(config_file: str) -> AppConfig:
    config_parser = ConfigParser(
        config_parser=configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation(),
        ),
        config_path=root_path(config_file),
    )
    return config_parser.parse()


def __bind_sub_configs(
    binder: Binder, app_config: AppConfig, logger: logging.Logger
) -> None:
    for _, value in app_config.__dict__.items():
        if isinstance(value, InjectableConfig) and value != None:
            logger.debug(f"Binding {type(value).__name__} to values {value}")
            binder.bind(type(value), value)


def __bind_logger(binder: Binder, app_config: AppConfig) -> logging.Logger:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "uvicorn": {  # rewrites uvicorn.error to uvicorn
                    "format": "%(asctime)s - uvicorn - %(levelname)s - %(message)s"
                },
                "brief": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "precise": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)s"
                },
            },
            "handlers": {
                "uvicorn": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "uvicorn",
                    "level": app_config.logging.log_level,
                },
                "console.brief": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "brief",
                    "level": app_config.logging.log_level,
                },
                "console.precise": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "precise",
                    "level": app_config.logging.log_level,
                },
            },
            "root": {
                "level": app_config.logging.log_level,
                "handlers": ["console.brief"],
            },
            "loggers": {
                "uvicorn.error": {
                    "level": "INFO",
                    "handlers": ["uvicorn"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["console.brief"],
                    "propagate": False,
                },
                app_config.logging.logger_name: {
                    "handlers": ["console.precise"],
                    "level": app_config.logging.log_level,
                    "propagate": False,
                },
            },
        }
    )

    logger = logging.getLogger(app_config.logging.logger_name)
    binder.bind(
        logging.Logger,
        logger,
    )
    return logger


def get_config() -> AppConfig:
    return inject.instance(AppConfig)


def __bind_resource_scanner(binder: Binder) -> None:
    binder.bind(ResourceScanner, ResourceScanner(resource_dir()))


def __bind_hcim_resource_matcher(binder: Binder) -> None:
    binder.bind(
        HCIMResourceMatcher, HCIMResourceMatcher(hcim_dir=project_root("app/hcim"))
    )


def __bind_span_processor(binder: Binder, app_config: AppConfig) -> None:
    binder.bind(
        SpanExporter,
        OTLPSpanExporterGRPC(
            endpoint=app_config.telemetry.collector_grpc_url, insecure=True
        ),
    )
