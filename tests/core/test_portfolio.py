"""Unit tests for portfolio and position management (Day 3, TDD)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from core.portfolio import Portfolio


def test_init_empty_portfolio() -> None:
    """Portfolio should initialize with empty positions and full cash."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")

    assert portfolio.cash == pytest.approx(100_000)
    assert portfolio.positions == {}
    assert portfolio.get_position("000001.SZ") is None


def test_buy_updates_position_and_cost() -> None:
    """Buying should update quantity, weighted cost, and cash."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")

    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=date(2026, 2, 12))

    position = portfolio.get_position("000001.SZ")
    assert position is not None
    assert position.quantity == 100
    assert position.cost == pytest.approx(10.0)
    assert position.available == 100
    assert portfolio.cash == pytest.approx(99_000)


def test_sell_updates_position_and_realized_pnl() -> None:
    """Selling should reduce position, increase cash, and return realized pnl."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    trade_date = date(2026, 2, 12)
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=trade_date)

    realized_pnl = portfolio.sell("000001.SZ", quantity=40, price=12.0, date=trade_date)

    position = portfolio.get_position("000001.SZ")
    assert position is not None
    assert position.quantity == 60
    assert position.available == 60
    assert realized_pnl == pytest.approx(80.0)
    assert portfolio.cash == pytest.approx(99_480)


def test_t0_can_sell_same_day() -> None:
    """T+0 mode should allow selling shares bought on the same day."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    trade_date = date(2026, 2, 12)

    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=trade_date)
    portfolio.sell("000001.SZ", quantity=100, price=10.5, date=trade_date)

    assert portfolio.get_position("000001.SZ") is None


def test_t1_cannot_sell_same_day_buys() -> None:
    """T+1 mode should block selling quantity bought on the same date."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+1")
    trade_date = date(2026, 2, 12)

    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=trade_date)

    with pytest.raises(ValueError, match="Insufficient available quantity"):
        portfolio.sell("000001.SZ", quantity=1, price=10.1, date=trade_date)


def test_available_quantity_in_t1_mode() -> None:
    """T+1 available quantity should update after settlement."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+1")
    d1 = date(2026, 2, 12)
    d2 = d1 + timedelta(days=1)

    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=d1)

    assert portfolio.get_available_quantity("000001.SZ", d1) == 0

    portfolio.settle_day(d1)

    assert portfolio.get_available_quantity("000001.SZ", d2) == 100


def test_weighted_average_cost() -> None:
    """Position cost should be updated using weighted-average method."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    d1 = date(2026, 2, 12)
    d2 = d1 + timedelta(days=1)

    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=d1)
    portfolio.buy("000001.SZ", quantity=200, price=11.0, date=d2)

    position = portfolio.get_position("000001.SZ")
    assert position is not None
    assert position.quantity == 300
    assert position.cost == pytest.approx((100 * 10.0 + 200 * 11.0) / 300)


def test_get_unrealized_pnl() -> None:
    """Unrealized PnL should be calculated by latest market prices."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=date(2026, 2, 12))

    pnl = portfolio.get_unrealized_pnl({"000001.SZ": 10.8})

    assert pnl == pytest.approx(80.0)


def test_get_total_value() -> None:
    """Total portfolio value should equal cash + market value of positions."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=date(2026, 2, 12))

    total_value = portfolio.get_total_value({"000001.SZ": 10.8})

    assert total_value == pytest.approx(100_080.0)


def test_get_position_ratios() -> None:
    """Position ratios should be market value divided by total assets."""
    portfolio = Portfolio(initial_cash=100_000, trade_mode="T+0")
    trade_date = date(2026, 2, 12)
    portfolio.buy("000001.SZ", quantity=100, price=10.0, date=trade_date)  # 1000
    portfolio.buy("000002.SZ", quantity=200, price=20.0, date=trade_date)  # 4000

    ratios = portfolio.get_position_ratios({"000001.SZ": 10.0, "000002.SZ": 20.0})

    assert ratios["000001.SZ"] == pytest.approx(1000 / 100000)
    assert ratios["000002.SZ"] == pytest.approx(4000 / 100000)
