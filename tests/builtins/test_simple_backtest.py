"""Simple backtest engine tests (Day 10, TDD)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from plugins.protocols import BacktestProtocol

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = PROJECT_ROOT / "contrib" / "backtest" / "simple_backtest.py"


def _load_engine_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("day10_simple_backtest", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load simple_backtest module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["day10_simple_backtest"] = module
    spec.loader.exec_module(module)
    return module


def _sample_data() -> list[dict[str, Any]]:
    return [
        {
            "date": date(2026, 1, 2),
            "symbol": "CB001",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
        },
        {
            "date": date(2026, 1, 3),
            "symbol": "CB001",
            "open": 101.0,
            "high": 103.0,
            "low": 100.0,
            "close": 102.0,
        },
        {
            "date": date(2026, 1, 4),
            "symbol": "CB001",
            "open": 102.0,
            "high": 104.0,
            "low": 101.0,
            "close": 103.0,
        },
    ]


def test_engine_initialization() -> None:
    module = _load_engine_module()

    engine = module.SimpleBacktestEngine(
        initial_cash=200_000,
        trade_mode="T+1",
        commission_rate=0.001,
        slippage=0.002,
    )

    assert engine.initial_cash == 200_000
    assert engine.trade_mode == "T+1"
    assert engine.commission_rate == 0.001
    assert engine.slippage == 0.002


def _expand_bar_records(bar: dict[str, Any]) -> list[dict[str, Any]]:
    cb_data = bar.get("cb_data")
    if isinstance(cb_data, list) and cb_data:
        return cb_data
    return [bar]


def _first_symbol(bar: dict[str, Any]) -> str:
    return _expand_bar_records(bar)[0]["symbol"]


def _series_dates(result: Any) -> list[str]:
    return [str(point["date"]) for point in result.net_value_series]


class _NoopStrategy:
    def on_init(self, context: Any) -> None:
        context.set("noop_initialized", True)

    def on_bar(self, context: Any, bar: dict[str, Any]) -> None:
        _ = (context, bar)
        return None


def test_data_loading_within_date_range() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(initial_cash=100_000)

    result = engine.run(
        strategy=_NoopStrategy(),
        data=_sample_data(),
        start_date=date(2026, 1, 3),
        end_date=date(2026, 1, 4),
    )

    series_dates = _series_dates(result)

    assert series_dates == ["2026-01-03", "2026-01-04"]


def test_match_market_order() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(slippage=0.001)

    trade = engine._match_order(
        {
            "symbol": "CB001",
            "side": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
        },
        {
            "symbol": "CB001",
            "date": date(2026, 1, 2),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
        },
    )

    assert trade is not None
    assert trade["price"] == 101.0 * 1.001


def test_match_limit_order() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine()

    trade = engine._match_order(
        {
            "symbol": "CB001",
            "side": "BUY",
            "quantity": 10,
            "order_type": "LIMIT",
            "price": 100.0,
        },
        {
            "symbol": "CB001",
            "date": date(2026, 1, 2),
            "open": 101.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.5,
        },
    )

    assert trade is not None
    assert trade["price"] == 100.0


class _SameDayRoundTripStrategy:
    def on_init(self, context: Any) -> None:
        _ = context

    def on_bar(self, context: Any, bar: dict[str, Any]) -> list[dict[str, Any]]:
        _ = context
        return [
            {
                "symbol": _first_symbol(bar),
                "side": "BUY",
                "quantity": 10,
                "order_type": "MARKET",
            },
            {
                "symbol": _first_symbol(bar),
                "side": "SELL",
                "quantity": 10,
                "order_type": "MARKET",
            },
        ]


def test_t0_mode_allows_same_day_sell() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(trade_mode="T+0")

    result = engine.run(
        strategy=_SameDayRoundTripStrategy(),
        data=[_sample_data()[0]],
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
    )

    assert result.trade_count == 2


def test_t1_mode_blocks_same_day_sell() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(trade_mode="T+1")

    result = engine.run(
        strategy=_SameDayRoundTripStrategy(),
        data=[_sample_data()[0]],
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
    )

    assert result.trade_count == 1


def test_commission_calculation() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(commission_rate=0.0005)

    commission = engine._calculate_commission(100_000)

    assert commission == 50.0


class _BuyAndHoldStrategy:
    def on_init(self, context: Any) -> None:
        _ = context

    def on_bar(self, context: Any, bar: dict[str, Any]) -> list[dict[str, Any]]:
        if context.get("bought", False):
            return []
        context.set("bought", True)
        return [
            {
                "symbol": _first_symbol(bar),
                "side": "BUY",
                "quantity": 10,
                "order_type": "MARKET",
            }
        ]


def test_net_value_series_generation() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(initial_cash=100_000, commission_rate=0.0)

    result = engine.run(
        strategy=_BuyAndHoldStrategy(),
        data=_sample_data(),
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    assert len(result.net_value_series) == 3
    assert result.net_value_series[-1]["value"] >= result.net_value_series[0]["value"]


def test_backtest_stats_metrics() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(initial_cash=100_000, commission_rate=0.0)

    result = engine.run(
        strategy=_BuyAndHoldStrategy(),
        data=_sample_data(),
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    assert result.total_return > 0
    assert isinstance(result.sharpe_ratio, float)
    assert result.max_drawdown >= 0


class _FullFlowStrategy:
    def on_init(self, context: Any) -> None:
        context.set("step", 0)

    def on_bar(self, context: Any, bar: dict[str, Any]) -> list[dict[str, Any]]:
        step = context.get("step", 0)
        context.set("step", step + 1)
        if step == 0:
            return [
                {
                    "symbol": _first_symbol(bar),
                    "side": "BUY",
                    "quantity": 10,
                    "order_type": "MARKET",
                }
            ]
        if step == 2:
            return [
                {
                    "symbol": _first_symbol(bar),
                    "side": "SELL",
                    "quantity": 10,
                    "order_type": "MARKET",
                }
            ]
        return []


def test_full_backtest_strategy_flow() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine(initial_cash=100_000)

    result = engine.run(
        strategy=_FullFlowStrategy(),
        data=_sample_data(),
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    assert result.trade_count == 2
    assert len(result.trades) == 2
    assert result.final_value > 0


def test_engine_implements_backtest_protocol() -> None:
    module = _load_engine_module()
    engine = module.SimpleBacktestEngine()

    assert isinstance(engine, BacktestProtocol)
