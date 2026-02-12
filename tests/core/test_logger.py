"""Unit tests for logging module (TDD for Day 3)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.logger import get_logger, setup_logging


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_default_logging_level_is_info() -> None:
    """Default setup should configure root logging level to INFO."""
    setup_logging({})

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_default_log_format_contains_timestamp_level_module_and_message(
    tmp_path: Path,
) -> None:
    """Default formatter should follow unified bracket-based format."""
    log_file = tmp_path / "format.log"
    setup_logging({"file_path": str(log_file)})

    logger = get_logger("core.test_logger")
    logger.info("hello-format")

    content = _read_text(log_file).strip()
    pattern = re.compile(r"^\[.+\] \[INFO\] \[core\.test_logger\] hello-format$")
    assert pattern.match(content) is not None


def test_all_main_levels_are_emitted_when_level_is_debug(tmp_path: Path) -> None:
    """DEBUG/INFO/WARNING/ERROR messages should all be emitted at DEBUG level."""
    log_file = tmp_path / "levels.log"
    setup_logging({"level": "DEBUG", "file_path": str(log_file)})

    logger = get_logger("core.levels")
    logger.debug("d")
    logger.info("i")
    logger.warning("w")
    logger.error("e")

    content = _read_text(log_file)
    assert "[DEBUG] [core.levels] d" in content
    assert "[INFO] [core.levels] i" in content
    assert "[WARNING] [core.levels] w" in content
    assert "[ERROR] [core.levels] e" in content


def test_file_handler_writes_logs(tmp_path: Path) -> None:
    """When file_path is provided, logs should be written to that file."""
    log_file = tmp_path / "app.log"
    setup_logging({"file_path": str(log_file)})

    get_logger("core.file").warning("to-file")

    assert log_file.exists()
    assert "to-file" in _read_text(log_file)


def test_console_handler_outputs_logs(capsys) -> None:  # type: ignore[no-untyped-def]
    """Logging should always emit to console via StreamHandler."""
    setup_logging({"level": "INFO"})

    get_logger("core.console").info("to-console")
    captured = capsys.readouterr()

    assert "to-console" in (captured.err + captured.out)


def test_log_level_filtering_respects_threshold(tmp_path: Path) -> None:
    """Messages below configured level should be filtered out."""
    log_file = tmp_path / "filter.log"
    setup_logging({"level": "WARNING", "file_path": str(log_file)})

    logger = get_logger("core.filter")
    logger.info("filtered")
    logger.warning("kept")

    content = _read_text(log_file)
    assert "filtered" not in content
    assert "kept" in content


def test_json_format_output(tmp_path: Path) -> None:
    """When json_format is enabled, each line should be valid JSON log."""
    log_file = tmp_path / "json.log"
    setup_logging({"level": "INFO", "file_path": str(log_file), "json_format": True})

    get_logger("core.json").info("json-message")

    record = json.loads(_read_text(log_file).strip())
    assert record["level"] == "INFO"
    assert record["name"] == "core.json"
    assert record["message"] == "json-message"
    assert "timestamp" in record


def test_log_context_extra_fields_in_json_output(tmp_path: Path) -> None:
    """Extra context fields should be preserved in structured JSON logs."""
    log_file = tmp_path / "context.log"
    setup_logging({"file_path": str(log_file), "json_format": True})

    get_logger("core.context").info(
        "ctx",
        extra={"strategy": "double_low", "run_id": "r-001"},
    )

    record = json.loads(_read_text(log_file).strip())
    assert record["strategy"] == "double_low"
    assert record["run_id"] == "r-001"
