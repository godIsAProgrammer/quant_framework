"""Risk management rules and manager for order/position checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping

from .portfolio import Portfolio, Position


@dataclass(slots=True)
class RiskCheckResult:
    """Result container for risk checks.

    Attributes:
        passed: Whether all risk checks passed.
        violations: Human-readable violation reasons.
    """

    passed: bool
    violations: list[str] = field(default_factory=list)


class RiskRule(ABC):
    """Abstract base class for all risk rules."""

    @abstractmethod
    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        """Validate an order against this rule and return violations."""

    @abstractmethod
    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        """Validate an existing position against this rule and return violations."""


class StopLossRule(RiskRule):
    """Trigger violation when current price falls below stop-loss threshold."""

    def __init__(self, stop_loss_pct: float) -> None:
        if not 0 < stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        self.stop_loss_pct = stop_loss_pct

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        _ = (order, portfolio, prices)
        return []

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        trigger_price = position.cost * (1 - self.stop_loss_pct)
        if price <= trigger_price:
            return [
                f"Stop loss triggered for {symbol}: price {price:.4f} <= {trigger_price:.4f}"
            ]
        return []


class TakeProfitRule(RiskRule):
    """Trigger violation when current price rises above take-profit threshold."""

    def __init__(self, take_profit_pct: float) -> None:
        if not 0 < take_profit_pct < 1:
            raise ValueError("take_profit_pct must be between 0 and 1")
        self.take_profit_pct = take_profit_pct

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        _ = (order, portfolio, prices)
        return []

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        trigger_price = position.cost * (1 + self.take_profit_pct)
        if price >= trigger_price:
            return [
                f"Take profit triggered for {symbol}: price {price:.4f} >= {trigger_price:.4f}"
            ]
        return []


class MaxPositionRatioRule(RiskRule):
    """Limit single-symbol market value ratio in total assets."""

    def __init__(self, max_ratio: float) -> None:
        if not 0 < max_ratio <= 1:
            raise ValueError("max_ratio must be in (0, 1]")
        self.max_ratio = max_ratio

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        side = _read_order_side(order)
        if side != "BUY":
            return []

        symbol = _read_order_symbol(order)
        quantity = _read_order_quantity(order)
        price = _read_order_price(order)

        total_value = portfolio.get_total_value(dict(prices))
        if total_value <= 0:
            return []

        position = portfolio.get_position(symbol)
        current_quantity = position.quantity if position is not None else 0
        current_price = prices.get(
            symbol, position.cost if position is not None else price
        )
        current_value = current_quantity * current_price

        projected_value = current_value + quantity * price
        ratio = projected_value / total_value

        if ratio > self.max_ratio:
            return [
                (
                    f"Position ratio violation for {symbol}: "
                    f"{ratio:.2%} > max ratio {self.max_ratio:.2%}"
                )
            ]
        return []

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        _ = (symbol, position, price)
        return []


class MaxHoldingsRule(RiskRule):
    """Limit the number of distinct symbols held in portfolio."""

    def __init__(self, max_holdings: int) -> None:
        if max_holdings <= 0:
            raise ValueError("max_holdings must be positive")
        self.max_holdings = max_holdings

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        _ = prices
        side = _read_order_side(order)
        if side != "BUY":
            return []

        symbol = _read_order_symbol(order)
        if symbol in portfolio.positions:
            return []

        if len(portfolio.positions) >= self.max_holdings:
            return [
                (
                    f"Max holdings violation: current {len(portfolio.positions)}, "
                    f"limit {self.max_holdings}"
                )
            ]
        return []

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        _ = (symbol, position, price)
        return []


class MaxTradeAmountRule(RiskRule):
    """Limit the amount of one single order."""

    def __init__(self, max_amount: float) -> None:
        if max_amount <= 0:
            raise ValueError("max_amount must be positive")
        self.max_amount = max_amount

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> list[str]:
        _ = (portfolio, prices)
        quantity = _read_order_quantity(order)
        price = _read_order_price(order)

        amount = quantity * price
        if amount > self.max_amount:
            return [
                f"Max trade amount violation: amount {amount:.2f} > max trade amount {self.max_amount:.2f}"
            ]
        return []

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> list[str]:
        _ = (symbol, position, price)
        return []


class RiskManager:
    """Risk manager that evaluates orders and positions against rules."""

    def __init__(self, rules: list[RiskRule] | None = None) -> None:
        self.rules: list[RiskRule] = list(rules) if rules is not None else []
        self._violations: list[str] = []

    def add_rule(self, rule: RiskRule) -> None:
        """Add one risk rule."""
        self.rules.append(rule)

    def check_order(
        self,
        order: Mapping[str, object],
        portfolio: Portfolio,
        prices: Mapping[str, float],
    ) -> RiskCheckResult:
        """Check whether an order passes all configured rules."""
        violations: list[str] = []
        for rule in self.rules:
            violations.extend(rule.check_order(order, portfolio, prices))

        self._violations = violations
        return RiskCheckResult(passed=len(violations) == 0, violations=violations)

    def check_position(
        self, symbol: str, position: Position, price: float
    ) -> RiskCheckResult:
        """Check whether a position triggers stop-loss/take-profit rules."""
        violations: list[str] = []
        for rule in self.rules:
            violations.extend(rule.check_position(symbol, position, price))

        self._violations = violations
        return RiskCheckResult(passed=len(violations) == 0, violations=violations)

    def get_violations(self) -> list[str]:
        """Get latest violation messages."""
        return list(self._violations)


def _read_order_symbol(order: Mapping[str, object]) -> str:
    raw = order.get("symbol")
    if not isinstance(raw, str) or raw == "":
        raise ValueError("order.symbol must be non-empty string")
    return raw


def _read_order_quantity(order: Mapping[str, object]) -> int:
    raw = order.get("quantity")
    if not isinstance(raw, int) or raw <= 0:
        raise ValueError("order.quantity must be positive int")
    return raw


def _read_order_price(order: Mapping[str, object]) -> float:
    raw = order.get("price")
    if isinstance(raw, int):
        value = float(raw)
    elif isinstance(raw, float):
        value = raw
    else:
        raise ValueError("order.price must be positive number")

    if value <= 0:
        raise ValueError("order.price must be positive number")
    return value


def _read_order_side(order: Mapping[str, object]) -> str:
    raw = order.get("side", "BUY")
    if not isinstance(raw, str) or raw == "":
        raise ValueError("order.side must be non-empty string")
    return raw.upper()
