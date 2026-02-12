"""Built-in hook specifications for the quant plugin framework."""

from __future__ import annotations

from typing import Any

from core.context import Context

from .hookspecs import hookspec


class QuantHookSpec:
    """Framework built-in hook contracts exposed to plugins."""

    @hookspec
    def on_init(self, context: Context) -> None:
        """Called when framework context has been initialized."""

    @hookspec
    def on_start(self, context: Context) -> None:
        """Called before strategy execution starts."""

    @hookspec
    def on_stop(self, context: Context) -> None:
        """Called before framework shutdown."""

    @hookspec
    def on_bar(self, context: Context, bar: dict[str, Any]) -> None:
        """Called for each bar market data event."""

    @hookspec(first_result=True)  # type: ignore[untyped-decorator]
    def on_order(
        self, context: Context, order: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Called before order submission for optional order mutation."""

    @hookspec
    def on_trade(self, context: Context, trade: dict[str, Any]) -> None:
        """Called when a trade execution event is received."""

    @hookspec(optional=True)  # type: ignore[untyped-decorator]
    def on_error(self, context: Context, error: Exception) -> None:
        """Called when runtime raises an error (optional)."""
