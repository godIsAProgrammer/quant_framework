"""Logging utilities for quant plugin framework.

This module provides a unified logging setup entrypoint and logger retrieval
helper.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, TypedDict


class LoggingSetupConfig(TypedDict, total=False):
    """Configuration options for :func:`setup_logging`.

    Attributes:
        level: Logging level name (e.g. ``"INFO"``) or integer level.
        format: Logging formatter pattern for text output.
        file_path: Optional file path for file handler output.
        json_format: Whether to output logs as JSON lines.
    """

    level: str | int
    format: str
    file_path: str
    json_format: bool


_DEFAULT_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_RESERVED_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format log records as one-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record into JSON.

        Args:
            record: Logging record.

        Returns:
            A JSON string containing core log fields and extra context fields.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info is not None:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Return a logger by name.

    Args:
        name: Logger name.

    Returns:
        Standard library logger instance.
    """
    return logging.getLogger(name)


def setup_logging(config: Mapping[str, Any] | None = None) -> None:
    """Configure root logging handlers and formatter.

    This function is idempotent in the sense that it removes and closes existing
    root handlers before applying a new setup.

    Args:
        config: Optional mapping with logging options.
    """
    conf = dict(config or {})

    level = _parse_level(conf.get("level", "INFO"))
    text_format = str(conf.get("format", _DEFAULT_FORMAT))
    file_path = conf.get("file_path")
    json_format = bool(conf.get("json_format", False))

    root_logger = logging.getLogger()

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(level)

    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(text_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if isinstance(file_path, str) and file_path:
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def _parse_level(level: str | int) -> int:
    """Convert level setting into a logging level integer."""
    if isinstance(level, int):
        return level

    level_name = level.upper()
    parsed_level = logging.getLevelName(level_name)
    if isinstance(parsed_level, int):
        return parsed_level

    return logging.INFO
