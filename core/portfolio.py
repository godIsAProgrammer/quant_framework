"""Portfolio and position management for trading simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

TradeMode = Literal["T+0", "T+1"]


@dataclass
class Position:
    """A single security position.

    Attributes:
        symbol: Instrument code.
        quantity: Total holding quantity.
        cost: Weighted average holding cost.
        available: Quantity available to sell.
        buy_date: Latest buy date for this symbol.
    """

    symbol: str
    quantity: int
    cost: float
    available: int
    buy_date: date | None = None


class Portfolio:
    """Portfolio manager with T+0/T+1 trading behavior."""

    def __init__(self, initial_cash: float, trade_mode: TradeMode = "T+0") -> None:
        """Initialize portfolio state.

        Args:
            initial_cash: Starting cash amount.
            trade_mode: Trading settlement rule, either ``T+0`` or ``T+1``.
        """
        if initial_cash < 0:
            raise ValueError("initial_cash must be non-negative")
        if trade_mode not in ("T+0", "T+1"):
            raise ValueError("trade_mode must be 'T+0' or 'T+1'")

        self.initial_cash: float = float(initial_cash)
        self.cash: float = float(initial_cash)
        self.positions: dict[str, Position] = {}
        self.trade_mode: TradeMode = trade_mode
        self._pending_t1: dict[date, dict[str, int]] = {}

    def buy(self, symbol: str, quantity: int, price: float, date: date) -> None:
        """Execute a buy trade and update position/cash.

        Args:
            symbol: Security symbol.
            quantity: Quantity to buy, positive integer.
            price: Trade price.
            date: Trade date.
        """
        self._validate_trade_input(symbol=symbol, quantity=quantity, price=price)

        amount = quantity * price
        if amount > self.cash:
            raise ValueError("Insufficient cash")

        self.cash -= amount

        existing = self.positions.get(symbol)
        if existing is None:
            available = quantity if self.trade_mode == "T+0" else 0
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                cost=price,
                available=available,
                buy_date=date,
            )
        else:
            total_cost = existing.cost * existing.quantity + amount
            total_quantity = existing.quantity + quantity
            existing.quantity = total_quantity
            existing.cost = total_cost / total_quantity
            existing.buy_date = date
            if self.trade_mode == "T+0":
                existing.available += quantity

        if self.trade_mode == "T+1":
            date_bucket = self._pending_t1.setdefault(date, {})
            date_bucket[symbol] = date_bucket.get(symbol, 0) + quantity

    def sell(self, symbol: str, quantity: int, price: float, date: date) -> float:
        """Execute a sell trade.

        Args:
            symbol: Security symbol.
            quantity: Quantity to sell, positive integer.
            price: Trade price.
            date: Trade date.

        Returns:
            Realized PnL for this trade.
        """
        _ = date
        self._validate_trade_input(symbol=symbol, quantity=quantity, price=price)

        position = self.positions.get(symbol)
        if position is None or position.quantity < quantity:
            raise ValueError("Insufficient position quantity")

        available = self.get_available_quantity(symbol, date)
        if quantity > available:
            raise ValueError("Insufficient available quantity")

        realized_pnl = (price - position.cost) * quantity
        self.cash += quantity * price

        position.quantity -= quantity
        position.available -= quantity

        if position.quantity == 0:
            del self.positions[symbol]
        elif self.trade_mode == "T+0":
            position.available = position.quantity

        return realized_pnl

    def get_position(self, symbol: str) -> Position | None:
        """Return position by symbol, or ``None`` if not found."""
        return self.positions.get(symbol)

    def get_available_quantity(self, symbol: str, date: date) -> int:
        """Get sellable quantity under current trade mode.

        Args:
            symbol: Security symbol.
            date: Query date.
        """
        _ = date
        position = self.positions.get(symbol)
        if position is None:
            return 0

        if self.trade_mode == "T+0":
            return position.quantity

        return position.available

    def get_total_value(self, prices: dict[str, float]) -> float:
        """Calculate total asset value using given market prices."""
        market_value = 0.0
        for symbol, position in self.positions.items():
            market_price = prices.get(symbol, position.cost)
            market_value += position.quantity * market_price
        return self.cash + market_value

    def get_unrealized_pnl(self, prices: dict[str, float]) -> float:
        """Calculate unrealized PnL from current holdings."""
        pnl = 0.0
        for symbol, position in self.positions.items():
            market_price = prices.get(symbol, position.cost)
            pnl += (market_price - position.cost) * position.quantity
        return pnl

    def settle_day(self, date: date) -> None:
        """Perform day-end settlement.

        For ``T+1`` mode, quantities bought on ``date`` become sellable.
        """
        if self.trade_mode != "T+1":
            return

        released = self._pending_t1.pop(date, {})
        for symbol, qty in released.items():
            position = self.positions.get(symbol)
            if position is not None:
                position.available += qty

    def get_position_ratios(self, prices: dict[str, float]) -> dict[str, float]:
        """Return each position's market value ratio to total assets."""
        total_value = self.get_total_value(prices)
        if total_value <= 0:
            return {symbol: 0.0 for symbol in self.positions}

        ratios: dict[str, float] = {}
        for symbol, position in self.positions.items():
            market_price = prices.get(symbol, position.cost)
            ratios[symbol] = (position.quantity * market_price) / total_value
        return ratios

    @staticmethod
    def _validate_trade_input(symbol: str, quantity: int, price: float) -> None:
        if not symbol:
            raise ValueError("symbol must not be empty")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
