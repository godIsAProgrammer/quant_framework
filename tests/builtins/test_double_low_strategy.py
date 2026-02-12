"""Double low convertible bond strategy tests (Day 9, TDD)."""

from __future__ import annotations

import importlib.util
import logging
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager
from plugins.protocols import StrategyProtocol

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_PATH = PROJECT_ROOT / "contrib" / "strategy" / "double_low.py"


def _load_strategy_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("day9_double_low", STRATEGY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load double_low module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["day9_double_low"] = module
    spec.loader.exec_module(module)
    return module


def _build_context() -> Context:
    return Context(
        config=FrameworkConfig(),
        portfolio=Portfolio(initial_cash=100_000),
        risk_manager=RiskManager(),
        event_engine=EventEngine(),
        logger=logging.getLogger("test.double_low"),
    )


def test_calculate_double_low_value() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()

    rows = strategy.calculate_double_low(
        [
            {
                "symbol": "CB001",
                "price": 100.0,
                "premium_rate": 0.20,
                "volume": 2_000_000,
                "days_to_maturity": 180,
            }
        ]
    )

    assert rows[0]["double_low"] == 120.0


def test_calculate_double_low_sorted_ascending() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()

    rows = strategy.calculate_double_low(
        [
            {
                "symbol": "CB001",
                "price": 100.0,
                "premium_rate": 0.30,
                "volume": 2_000_000,
                "days_to_maturity": 180,
            },
            {
                "symbol": "CB002",
                "price": 99.0,
                "premium_rate": 0.20,
                "volume": 2_000_000,
                "days_to_maturity": 180,
            },
            {
                "symbol": "CB003",
                "price": 103.0,
                "premium_rate": 0.40,
                "volume": 2_000_000,
                "days_to_maturity": 180,
            },
        ]
    )

    assert [item["symbol"] for item in rows] == ["CB002", "CB001", "CB003"]


def test_select_top_n() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    strategy.top_n = 2

    top_codes = strategy.select_top_n(
        [
            {"symbol": "CB001", "double_low": 100.0},
            {"symbol": "CB002", "double_low": 101.0},
            {"symbol": "CB003", "double_low": 102.0},
        ]
    )

    assert top_codes == ["CB001", "CB002"]


def test_calculate_double_low_filters_by_volume_and_maturity() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    strategy.min_volume = 1_000_000
    strategy.exclude_days_to_maturity = 30

    rows = strategy.calculate_double_low(
        [
            {
                "symbol": "LOWVOL",
                "price": 100.0,
                "premium_rate": 0.10,
                "volume": 900_000,
                "days_to_maturity": 100,
            },
            {
                "symbol": "NEARMAT",
                "price": 100.0,
                "premium_rate": 0.10,
                "volume": 2_000_000,
                "days_to_maturity": 10,
            },
            {
                "symbol": "PASS",
                "price": 100.0,
                "premium_rate": 0.10,
                "volume": 2_000_000,
                "days_to_maturity": 100,
            },
        ]
    )

    assert [item["symbol"] for item in rows] == ["PASS"]


def test_generate_buy_signals() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    context = _build_context()

    signals = strategy.generate_signals(context, ["CB001", "CB002"])

    assert {signal.symbol for signal in signals if signal.direction == "BUY"} == {
        "CB001",
        "CB002",
    }


def test_generate_sell_signals_for_non_top_positions() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    context = _build_context()
    context.portfolio.buy("OLD", quantity=10, price=100.0, date=date(2026, 2, 12))

    signals = strategy.generate_signals(context, top_codes=[])

    assert len(signals) == 1
    assert signals[0].symbol == "OLD"
    assert signals[0].direction == "SELL"


def test_on_init_sets_state() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    context = _build_context()

    strategy.on_init(context)

    assert context.get("double_low_initialized") is True
    assert context.get("double_low_last_rebalance_date") is None


def test_strategy_implements_strategy_protocol() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()

    assert isinstance(strategy, StrategyProtocol)


def test_on_bar_executes_strategy_and_updates_rebalance_date() -> None:
    module = _load_strategy_module()
    strategy = module.DoubleLowStrategy()
    strategy.top_n = 1
    strategy.min_volume = 1
    context = _build_context()
    context.portfolio.buy("OLD", quantity=10, price=100.0, date=date(2026, 2, 10))

    signals = strategy.on_bar(
        context,
        {
            "date": date(2026, 2, 12),
            "cb_data": [
                {
                    "symbol": "NEW",
                    "price": 99.0,
                    "premium_rate": 0.10,
                    "volume": 2_000_000,
                    "days_to_maturity": 100,
                },
                {
                    "symbol": "OLD",
                    "price": 120.0,
                    "premium_rate": 0.30,
                    "volume": 2_000_000,
                    "days_to_maturity": 100,
                },
            ],
        },
    )

    assert {signal.direction for signal in signals} == {"BUY", "SELL"}
    assert context.get("double_low_last_rebalance_date") == date(2026, 2, 12)
