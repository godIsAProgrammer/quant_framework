"""Configuration management for quant plugin framework."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import tomllib
from pydantic import BaseModel, ConfigDict, Field


class EngineConfig(BaseModel):
    """Runtime settings for event engine."""

    model_config = ConfigDict(extra="forbid")

    worker_count: int = Field(default=1, ge=1)
    queue_size: int = Field(default=10_000, ge=1)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"
    format: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"


class PluginsConfig(BaseModel):
    """Plugin loading configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: list[str] = Field(default_factory=list)
    autoload: bool = True


class FrameworkConfig(BaseModel):
    """Top-level framework configuration model."""

    model_config = ConfigDict(extra="forbid")

    environment: Literal["dev", "test", "prod"] = "dev"
    engine: EngineConfig = Field(default_factory=EngineConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)


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
        """Validate configuration from dict, merged onto defaults."""
        merged = _deep_merge(
            self._defaults.model_dump(mode="python"),
            data,
        )
        return FrameworkConfig.model_validate(merged)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
