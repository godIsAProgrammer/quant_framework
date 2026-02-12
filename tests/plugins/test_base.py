"""Unit tests for plugin base class and protocol contracts (Day 6, TDD)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskCheckResult, RiskManager
from plugins.base import Plugin
from plugins.protocols import (
    BacktestProtocol,
    BacktestResult,
    DataSourceProtocol,
    RiskProtocol,
    Signal,
    StrategyProtocol,
)


@dataclass(slots=True)
class _DummyRiskResult:
    allowed: bool


def _build_context() -> Context:
    return Context(
        config=FrameworkConfig(),
        portfolio=Portfolio(initial_cash=100_000),
        risk_manager=RiskManager(),
        event_engine=EventEngine(),
        logger=logging.getLogger("test.plugins.base"),
    )


def test_plugin_base_attributes() -> None:
    """Plugin should expose name/version/description/dependencies attributes."""

    class DemoPlugin(Plugin):
        name = "demo"
        version = "1.2.3"
        description = "Demo plugin"
        dependencies = ["dep-a", "dep-b"]

    plugin = DemoPlugin()

    assert plugin.name == "demo"
    assert plugin.version == "1.2.3"
    assert plugin.description == "Demo plugin"
    assert plugin.dependencies == ["dep-a", "dep-b"]


def test_plugin_lifecycle_methods() -> None:
    """Plugin setup/teardown hooks should be callable with a Context."""

    class LifecyclePlugin(Plugin):
        def __init__(self) -> None:
            super().__init__()
            self.setup_called = False
            self.teardown_called = False

        def setup(self, context: Context) -> None:
            super().setup(context)
            self.setup_called = True

        def teardown(self, context: Context) -> None:
            super().teardown(context)
            self.teardown_called = True

    plugin = LifecyclePlugin()
    ctx = _build_context()

    plugin.setup(ctx)
    plugin.teardown(ctx)

    assert plugin.setup_called is True
    assert plugin.teardown_called is True


def test_plugin_enable_disable() -> None:
    """Plugin should support enable/disable state toggling."""
    plugin = Plugin()

    assert plugin.enabled is True

    plugin.disable()
    assert plugin.enabled is False

    plugin.enable()
    assert plugin.enabled is True


def test_plugin_dependencies_declaration() -> None:
    """Dependencies list should be instance-safe and mutable per plugin."""
    plugin_a = Plugin()
    plugin_b = Plugin()

    plugin_a.dependencies.append("core-feed")

    assert plugin_a.dependencies == ["core-feed"]
    assert plugin_b.dependencies == []


def test_data_source_protocol() -> None:
    """Data source implementation should satisfy DataSourceProtocol."""

    class DataSourceImpl:
        def fetch_bars(
            self, symbol: str, start: date, end: date
        ) -> list[dict[str, Any]]:
            _ = (symbol, start, end)
            return [{"symbol": "AAPL", "close": 100.0}]

        def fetch_realtime(self, symbol: str) -> dict[str, Any]:
            _ = symbol
            return {"symbol": "AAPL", "last": 101.0}

    impl = DataSourceImpl()

    assert isinstance(impl, DataSourceProtocol)


def test_strategy_protocol() -> None:
    """Strategy implementation should satisfy StrategyProtocol."""

    class StrategyImpl:
        def on_bar(self, context: Context, bar: dict[str, Any]) -> Signal | None:
            _ = context
            if bar.get("close", 0) > 0:
                return {"symbol": "AAPL", "action": "BUY"}
            return None

        def on_init(self, context: Context) -> None:
            context.set("initialized", True)

    impl = StrategyImpl()

    assert isinstance(impl, StrategyProtocol)


def test_risk_protocol() -> None:
    """Risk implementation should satisfy RiskProtocol."""

    class RiskImpl:
        def check_order(
            self, order: dict[str, Any], context: Context
        ) -> RiskCheckResult:
            _ = (order, context)
            return RiskCheckResult(passed=True)

    impl = RiskImpl()

    assert isinstance(impl, RiskProtocol)


def test_backtest_protocol() -> None:
    """Backtest implementation should satisfy BacktestProtocol."""

    class StrategyImpl:
        def on_bar(self, context: Context, bar: dict[str, Any]) -> Signal | None:
            _ = (context, bar)
            return None

        def on_init(self, context: Context) -> None:
            _ = context

    class BacktestImpl:
        def run(
            self,
            strategy: StrategyProtocol,
            data: list[dict[str, Any]],
            config: dict[str, Any],
        ) -> BacktestResult:
            _ = (strategy, data, config)
            return {"total_return": 0.12, "max_drawdown": 0.05}

    impl = BacktestImpl()

    assert isinstance(impl, BacktestProtocol)
