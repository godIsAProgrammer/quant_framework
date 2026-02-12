"""Protocol definitions for plugin capability contracts."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from core.context import Context
from core.risk import RiskCheckResult

Signal = dict[str, Any]
BacktestResult = dict[str, Any]


@runtime_checkable
class DataSourceProtocol(Protocol):
    """Contract for market data source plugins."""

    def fetch_bars(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch historical bars for a symbol in [start, end]."""

    def fetch_realtime(self, symbol: str) -> dict[str, Any]:
        """Fetch latest realtime quote/tick for a symbol."""


@runtime_checkable
class StrategyProtocol(Protocol):
    """Contract for strategy plugins."""

    def on_bar(self, context: Context, bar: dict[str, Any]) -> Signal | None:
        """Handle one bar event and optionally emit a signal."""

    def on_init(self, context: Context) -> None:
        """Initialize strategy state before running."""


@runtime_checkable
class RiskProtocol(Protocol):
    """Contract for risk plugins."""

    def check_order(self, order: dict[str, Any], context: Context) -> RiskCheckResult:
        """Validate one order request against risk constraints."""


@runtime_checkable
class BacktestProtocol(Protocol):
    """Contract for backtest engine plugins."""

    def run(
        self,
        strategy: StrategyProtocol,
        data: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> BacktestResult:
        """Run backtest and return summary/result payload."""
