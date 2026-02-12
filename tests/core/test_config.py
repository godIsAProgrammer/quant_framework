"""Unit tests for configuration manager (TDD for Day 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.config import ConfigManager


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_load_toml_config_file(tmp_path: Path) -> None:
    """ConfigManager should load and parse TOML configuration."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [app]
        name = "quant-framework"
        debug = true

        [strategy]
        name = "double_low"
        params = { top_n = 20, min_volume = 2000000 }

        [data_source]
        provider = "akshare"
        cache_dir = ".cache"

        [risk]
        max_position_ratio = 0.4
        stop_loss_ratio = 0.08
        """,
    )

    config = ConfigManager().load(config_file)

    assert config.app.name == "quant-framework"
    assert config.app.debug is True
    assert config.strategy.name == "double_low"
    assert config.strategy.params.top_n == 20
    assert config.data_source.provider == "akshare"
    assert config.risk.max_position_ratio == pytest.approx(0.4)


def test_pydantic_model_validation_for_ratio_range(tmp_path: Path) -> None:
    """Invalid ratio values should fail pydantic validation."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [risk]
        max_position_ratio = 1.2
        stop_loss_ratio = 0.05
        """,
    )

    with pytest.raises(ValidationError):
        ConfigManager().load(config_file)


def test_default_values_when_section_or_fields_missing(tmp_path: Path) -> None:
    """Missing config fields should be filled with model defaults."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [strategy]
        name = "double_low"
        """,
    )

    config = ConfigManager().load(config_file)

    assert config.app.name == "quant-framework"
    assert config.app.debug is False
    assert config.strategy.params.top_n == 10
    assert config.strategy.params.min_volume == 1_000_000
    assert config.data_source.provider == "akshare"
    assert config.risk.stop_loss_ratio == pytest.approx(0.05)


def test_dot_access_for_nested_config_values(tmp_path: Path) -> None:
    """Configuration should support dot-style nested field access."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [strategy]
        name = "double_low"
        params = { top_n = 15, min_volume = 3000000 }
        """,
    )

    config = ConfigManager().load(config_file)

    assert config.strategy.name == "double_low"
    assert config.strategy.params.top_n == 15


def test_missing_config_file_raises_file_not_found(tmp_path: Path) -> None:
    """Loading a non-existent config file should raise FileNotFoundError."""
    missing_file = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError):
        ConfigManager().load(missing_file)


def test_type_error_in_config_raises_validation_error(tmp_path: Path) -> None:
    """Wrong field types should trigger pydantic ValidationError."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [strategy]
        name = "double_low"
        params = { top_n = "ten", min_volume = 1000000 }
        """,
    )

    with pytest.raises(ValidationError):
        ConfigManager().load(config_file)
