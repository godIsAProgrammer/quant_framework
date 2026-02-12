"""Unit tests for configuration manager (Day 15, TDD)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.config import ConfigManager


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_load_day15_toml_schema(tmp_path: Path) -> None:
    """ConfigManager should load the Day 15 TOML schema."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [asset]
        type = "cb"

        [asset.params]
        price_max = 120
        premium_max = 30
        top_n = 3

        [strategy]
        name = "double_low"

        [strategy.params]
        price_max = 120
        premium_max = 30
        top_n = 3

        [data_source]
        primary = "akshare"
        backup = "tushare"

        [backtest]
        initial_capital = 100000
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        fee_rate = 0.0001
        """,
    )

    config = ConfigManager().load(config_file)

    assert config.asset.type == "cb"
    assert config.strategy.name == "double_low"
    assert config.strategy.params.top_n == 3
    assert config.data_source.primary == "akshare"
    assert config.data_source.backup == "tushare"
    assert config.backtest.initial_capital == pytest.approx(100000)


def test_asset_type_defaults_are_present() -> None:
    """asset_types should include stock/cb default trading specs."""
    cfg = ConfigManager().defaults

    assert cfg.asset_types["stock"].settlement == "T+1"
    assert cfg.asset_types["stock"].lot_size == 100
    assert cfg.asset_types["stock"].fee_rate == pytest.approx(0.0003)

    assert cfg.asset_types["cb"].settlement == "T+0"
    assert cfg.asset_types["cb"].lot_size == 10
    assert cfg.asset_types["cb"].fee_rate == pytest.approx(0.0001)


def test_macd_strategy_params_validation() -> None:
    """MACD params should enforce fast < slow."""
    with pytest.raises(ValidationError):
        ConfigManager().from_dict(
            {
                "strategy": {
                    "name": "macd",
                    "params": {"fast": 26, "slow": 12, "signal": 9},
                }
            }
        )


def test_backtest_date_range_validation() -> None:
    """backtest.end_date must be >= backtest.start_date."""
    with pytest.raises(ValidationError):
        ConfigManager().from_dict(
            {
                "backtest": {
                    "start_date": "2025-01-02",
                    "end_date": "2025-01-01",
                }
            }
        )


def test_env_override_support(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Environment variables should override file values."""
    config_file = tmp_path / "config.toml"
    _write_toml(
        config_file,
        """
        [asset]
        type = "stock"

        [strategy]
        name = "double_low"

        [strategy.params]
        price_max = 120
        premium_max = 30
        top_n = 3

        [data_source]
        primary = "akshare"
        backup = "tushare"

        [backtest]
        initial_capital = 100000
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        fee_rate = 0.0001
        """,
    )

    monkeypatch.setenv("QUANT__ASSET__TYPE", "cb")
    monkeypatch.setenv("QUANT__BACKTEST__INITIAL_CAPITAL", "200000")
    monkeypatch.setenv("QUANT__DATA_SOURCE__PRIMARY", '"tushare"')

    cfg = ConfigManager().load(config_file)

    assert cfg.asset.type == "cb"
    assert cfg.backtest.initial_capital == pytest.approx(200000)
    assert cfg.data_source.primary == "tushare"


def test_missing_config_file_raises_file_not_found(tmp_path: Path) -> None:
    """Loading a non-existent config file should raise FileNotFoundError."""
    missing_file = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError):
        ConfigManager().load(missing_file)
