"""Unit tests for risk management module (Day 4, TDD)."""

from __future__ import annotations

from datetime import date

import pytest

from core.portfolio import Portfolio
from core.risk import (
    MaxHoldingsRule,
    MaxPositionRatioRule,
    MaxTradeAmountRule,
    RiskManager,
    StopLossRule,
    TakeProfitRule,
)


def _build_order(
    symbol: str,
    quantity: int,
    price: float,
    side: str = "BUY",
) -> dict[str, object]:
    return {"symbol": symbol, "quantity": quantity, "price": price, "side": side}


def test_stop_loss_triggered_when_price_breaks_down() -> None:
    """Stop-loss should trigger when price is below threshold."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=date(2026, 2, 12))
    position = portfolio.get_position("000001.SZ")
    assert position is not None

    manager = RiskManager(rules=[StopLossRule(stop_loss_pct=0.1)])
    result = manager.check_position("000001.SZ", position, price=8.9)

    assert result.passed is False
    assert any("stop loss" in item.lower() for item in result.violations)


def test_take_profit_triggered_when_price_breaks_up() -> None:
    """Take-profit should trigger when price exceeds threshold."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=date(2026, 2, 12))
    position = portfolio.get_position("000001.SZ")
    assert position is not None

    manager = RiskManager(rules=[TakeProfitRule(take_profit_pct=0.2)])
    result = manager.check_position("000001.SZ", position, price=12.1)

    assert result.passed is False
    assert any("take profit" in item.lower() for item in result.violations)


def test_max_position_ratio_limit() -> None:
    """Single-symbol position ratio should not exceed configured limit."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    manager = RiskManager(rules=[MaxPositionRatioRule(max_ratio=0.5)])

    order = _build_order("000001.SZ", quantity=6000, price=10.0)
    result = manager.check_order(order, portfolio, prices={"000001.SZ": 10.0})

    assert result.passed is False
    assert any("position ratio" in item.lower() for item in result.violations)


def test_max_holdings_count_limit() -> None:
    """Buying a new symbol should be blocked when holdings count reaches max."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    trade_date = date(2026, 2, 12)
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=trade_date)
    portfolio.buy("000002.SZ", quantity=100, price=10.0, date=trade_date)

    manager = RiskManager(rules=[MaxHoldingsRule(max_holdings=2)])
    order = _build_order("000003.SZ", quantity=100, price=10.0)
    result = manager.check_order(
        order,
        portfolio,
        prices={"000001.SZ": 10.0, "000002.SZ": 10.0, "000003.SZ": 10.0},
    )

    assert result.passed is False
    assert any("max holdings" in item.lower() for item in result.violations)


def test_max_trade_amount_limit() -> None:
    """Single order amount should not exceed configured ceiling."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    manager = RiskManager(rules=[MaxTradeAmountRule(max_amount=20_000)])

    order = _build_order("000001.SZ", quantity=3000, price=10.0)
    result = manager.check_order(order, portfolio, prices={"000001.SZ": 10.0})

    assert result.passed is False
    assert any("trade amount" in item.lower() for item in result.violations)


def test_combined_rules_return_multiple_violations() -> None:
    """Risk manager should aggregate violations from multiple active rules."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    manager = RiskManager(
        rules=[
            MaxTradeAmountRule(max_amount=20_000),
            MaxPositionRatioRule(max_ratio=0.3),
        ]
    )

    order = _build_order("000001.SZ", quantity=4000, price=10.0)
    result = manager.check_order(order, portfolio, prices={"000001.SZ": 10.0})

    assert result.passed is False
    assert len(result.violations) >= 2
    assert any("trade amount" in item.lower() for item in result.violations)
    assert any("position ratio" in item.lower() for item in result.violations)


def test_risk_check_passes_when_all_rules_satisfied() -> None:
    """Order should pass when no rule is violated."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    manager = RiskManager(
        rules=[
            MaxTradeAmountRule(max_amount=50_000),
            MaxPositionRatioRule(max_ratio=0.5),
            MaxHoldingsRule(max_holdings=5),
        ]
    )

    order = _build_order("000001.SZ", quantity=1000, price=10.0)
    result = manager.check_order(order, portfolio, prices={"000001.SZ": 10.0})

    assert result.passed is True
    assert result.violations == []


def test_risk_blocks_order_and_returns_reason() -> None:
    """When blocked, result should include readable violation reasons."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    manager = RiskManager(rules=[MaxTradeAmountRule(max_amount=10_000)])

    order = _build_order("000001.SZ", quantity=2000, price=10.0)
    result = manager.check_order(order, portfolio, prices={"000001.SZ": 10.0})

    assert result.passed is False
    assert result.violations
    assert "max trade amount" in result.violations[0].lower()
