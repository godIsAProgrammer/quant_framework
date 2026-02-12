"""Tests for basic risk plugin (Day 11, TDD)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager
from plugins.protocols import RiskProtocol


def _expand_bar_records(bar: dict[str, Any]) -> list[dict[str, Any]]:
    cb_data = bar.get("cb_data")
    if isinstance(cb_data, list) and cb_data:
        return cb_data
    return [bar]


def _first_record(bar: dict[str, Any]) -> dict[str, Any]:
    return _expand_bar_records(bar)[0]


def _build_context(initial_cash: float = 100_000) -> Context:
    return Context(
        config=FrameworkConfig(),
        portfolio=Portfolio(initial_cash=initial_cash, trade_mode="T+0"),
        risk_manager=RiskManager(),
        event_engine=EventEngine(),
        logger=logging.getLogger("test.contrib.basic_risk"),
    )


def test_plugin_initialization() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    plugin = BasicRiskPlugin()

    assert plugin.name == "basic_risk"
    assert plugin.version == "1.0.0"
    assert plugin.max_position_ratio == 0.3
    assert plugin.max_trade_ratio == 0.2
    assert isinstance(plugin, RiskProtocol)


def test_max_position_ratio_check() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    plugin = BasicRiskPlugin()
    context = _build_context(initial_cash=100_000)

    # 40,000 / 100,000 = 40% > 30% -> reject
    order = {"symbol": "000001.SZ", "side": "BUY", "quantity": 400, "price": 100.0}
    result = plugin.check_order(order, context)

    assert result.passed is False
    assert any("position" in v.lower() for v in result.violations)


def test_max_trade_amount_check() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    plugin = BasicRiskPlugin()
    context = _build_context(initial_cash=100_000)

    # 30,000 > 100,000 * 20% (=20,000) -> reject
    order = {"symbol": "000001.SZ", "side": "BUY", "quantity": 300, "price": 100.0}
    result = plugin.check_order(order, context)

    assert result.passed is False
    assert any("trade" in v.lower() for v in result.violations)


def test_order_risk_check_pass() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    plugin = BasicRiskPlugin()
    context = _build_context(initial_cash=100_000)

    # 10,000 -> within both limits
    order = {"symbol": "000001.SZ", "side": "BUY", "quantity": 100, "price": 100.0}
    result = plugin.check_order(order, context)

    assert result.passed is True
    assert result.violations == []


def test_order_risk_check_reject_via_hook() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    plugin = BasicRiskPlugin()
    context = _build_context(initial_cash=100_000)

    order = {"symbol": "000001.SZ", "side": "BUY", "quantity": 400, "price": 100.0}
    blocked = plugin.on_order(context, order)

    assert blocked is None


def test_risk_rules_are_configurable() -> None:
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    # Relaxed config: 50% position, 40% trade
    plugin = BasicRiskPlugin(max_position_ratio=0.5, max_trade_ratio=0.4)
    context = _build_context(initial_cash=100_000)

    # 35,000 should pass under relaxed config
    order = {"symbol": "000001.SZ", "side": "BUY", "quantity": 350, "price": 100.0}
    result = plugin.check_order(order, context)

    assert result.passed is True


def test_integration_with_simple_backtest_engine() -> None:
    from contrib.backtest.simple_backtest import SimpleBacktestEngine
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    class StrategyWithRisk:
        def __init__(self, plugin: BasicRiskPlugin) -> None:
            self.plugin = plugin
            self.initialized = False

        def on_init(self, context: Context) -> None:
            self.plugin.setup(context)
            self.initialized = True

        def on_bar(self, context: Context, bar: dict[str, Any]) -> list[dict[str, Any]]:
            if not self.initialized:
                return []

            record = _first_record(bar)
            raw_order = {
                "symbol": record["symbol"],
                "side": "BUY",
                "quantity": 100,
                "price": float(record["close"]),
                "order_type": "MARKET",
            }
            checked = self.plugin.on_order(context, raw_order)
            return [checked] if checked is not None else []

    plugin = BasicRiskPlugin(max_position_ratio=0.3, max_trade_ratio=0.2)
    strategy = StrategyWithRisk(plugin)
    engine = SimpleBacktestEngine(
        initial_cash=100_000, commission_rate=0.0, slippage=0.0
    )

    bars = [
        {
            "date": date(2026, 2, 12),
            "symbol": "000001.SZ",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
        }
    ]

    result = engine.run(
        strategy=strategy,
        data=bars,
        start_date=date(2026, 2, 12),
        end_date=date(2026, 2, 12),
    )

    assert result.trade_count == 1
