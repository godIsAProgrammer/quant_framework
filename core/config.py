"""Configuration management for quant plugin framework."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Literal

import tomllib
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class AppConfig(BaseModel):
    """Application runtime config."""

    model_config = ConfigDict(extra="allow")

    name: str = "quant-framework"
    debug: bool = False


class AssetTypeSpec(BaseModel):
    """Trading rules for one asset type."""

    model_config = ConfigDict(extra="forbid")

    settlement: Literal["T+0", "T+1"]
    lot_size: int = Field(ge=1)
    fee_rate: float = Field(gt=0, le=0.01)


class AssetConfig(BaseModel):
    """Selected runtime asset configuration."""

    model_config = ConfigDict(extra="allow")

    type: Literal["stock", "cb"] = "cb"
    params: dict[str, Any] = Field(default_factory=dict)


class DoubleLowParams(BaseModel):
    """Parameters for double-low strategy."""

    model_config = ConfigDict(extra="allow")

    price_max: float = Field(default=120.0, gt=0)
    premium_max: float = Field(default=30.0, ge=0)
    top_n: int = Field(default=3, ge=1)


class MACDParams(BaseModel):
    """Parameters for MACD strategy."""

    model_config = ConfigDict(extra="allow")

    fast: int = Field(default=12, ge=1)
    slow: int = Field(default=26, ge=1)
    signal: int = Field(default=9, ge=1)

    @model_validator(mode="after")
    def _validate_periods(self) -> "MACDParams":
        if self.fast >= self.slow:
            raise ValueError("macd.fast must be less than macd.slow")
        return self


class StrategyConfig(BaseModel):
    """Strategy selection and parameters."""

    model_config = ConfigDict(extra="allow")

    name: Literal["double_low", "macd"] = "double_low"
    params: DoubleLowParams | MACDParams = Field(default_factory=DoubleLowParams)

    @model_validator(mode="before")
    @classmethod
    def _coerce_params_by_name(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        strategy_name = data.get("name", "double_low")
        raw_params = data.get("params", {})

        if strategy_name == "double_low":
            data["params"] = DoubleLowParams.model_validate(raw_params)
        elif strategy_name == "macd":
            data["params"] = MACDParams.model_validate(raw_params)
        return data


class DataSourceConfig(BaseModel):
    """Market data provider config."""

    model_config = ConfigDict(extra="allow")

    primary: Literal["akshare", "tushare"] = "akshare"
    backup: Literal["akshare", "tushare"] = "tushare"
    cache_dir: str = ".cache"


class BacktestConfig(BaseModel):
    """Backtest runtime parameters."""

    model_config = ConfigDict(extra="allow")

    initial_capital: float = Field(default=100000.0, gt=0)
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2024, 12, 31)
    fee_rate: float = Field(default=0.0001, ge=0, le=0.01)

    @model_validator(mode="after")
    def _validate_date_range(self) -> "BacktestConfig":
        if self.end_date < self.start_date:
            raise ValueError("backtest.end_date must be >= backtest.start_date")
        return self


class RiskConfig(BaseModel):
    """Risk control limits."""

    model_config = ConfigDict(extra="allow")

    max_position_ratio: float = Field(default=0.3, gt=0.0, le=1.0)
    stop_loss_ratio: float = Field(default=0.05, gt=0.0, le=1.0)


class EngineConfig(BaseModel):
    """Runtime settings for event engine."""

    model_config = ConfigDict(extra="allow")

    worker_count: int = Field(default=1, ge=1)
    queue_size: int = Field(default=10_000, ge=1)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="allow")

    level: str = "INFO"
    format: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"


class PluginsConfig(BaseModel):
    """Plugin loading configuration."""

    model_config = ConfigDict(extra="allow")

    enabled: list[str] = Field(default_factory=list)
    autoload: bool = True


class FrameworkConfig(BaseModel):
    """Top-level framework configuration model."""

    model_config = ConfigDict(extra="allow")

    app: AppConfig = Field(default_factory=AppConfig)

    asset_types: dict[Literal["stock", "cb"], AssetTypeSpec] = Field(
        default_factory=lambda: {
            "stock": AssetTypeSpec(settlement="T+1", lot_size=100, fee_rate=0.0003),
            "cb": AssetTypeSpec(settlement="T+0", lot_size=10, fee_rate=0.0001),
        }
    )
    asset: AssetConfig = Field(default_factory=AssetConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)

    # Backward-compatible fields used by earlier examples/exports
    environment: Literal["dev", "test", "prod"] = "dev"
    engine: EngineConfig = Field(default_factory=EngineConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)


class ConfigManager:
    """Load and validate framework configuration from TOML files."""

    def __init__(self, defaults: FrameworkConfig | None = None) -> None:
        self._defaults = defaults or FrameworkConfig()

    @property
    def defaults(self) -> FrameworkConfig:
        """Return default configuration."""
        return self._defaults

    def load(self, path: str | Path) -> FrameworkConfig:
        """Load TOML file and merge with defaults before validation."""
        config_path = Path(path)
        with config_path.open("rb") as f:
            data = tomllib.load(f)

        return self.from_dict(data)

    def from_dict(self, data: dict[str, Any]) -> FrameworkConfig:
        """Validate configuration from dict, merged onto defaults and env vars."""
        merged = _deep_merge(
            self._defaults.model_dump(mode="python"),
            data,
        )
        merged_with_env = _apply_env_overrides(merged)
        return FrameworkConfig.model_validate(merged_with_env)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply env overrides using QUANT__A__B style keys."""
    overridden = deepcopy(config)

    for key, raw_value in os.environ.items():
        if not key.startswith("QUANT__"):
            continue

        path = key[len("QUANT__") :].strip("_")
        if not path:
            continue

        keys = [part.lower() for part in path.split("__") if part]
        if not keys:
            continue

        _set_nested(overridden, keys, _parse_env_value(raw_value))

    return overridden


def _set_nested(root: dict[str, Any], keys: list[str], value: Any) -> None:
    current: dict[str, Any] = root
    for key in keys[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[keys[-1]] = value


def _parse_env_value(raw: str) -> Any:
    lowered = raw.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
