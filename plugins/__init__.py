"""Plugin abstractions for quant plugin framework."""

from .base import Plugin
from .protocols import (
    BacktestProtocol,
    BacktestResult,
    DataSourceProtocol,
    RiskProtocol,
    Signal,
    StrategyProtocol,
)

__all__ = [
    "Plugin",
    "Signal",
    "BacktestResult",
    "DataSourceProtocol",
    "StrategyProtocol",
    "RiskProtocol",
    "BacktestProtocol",
]
