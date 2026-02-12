"""Execution context management for strategy runtime.

This module provides a context container for framework components and a
``ContextVar``-based current-context mechanism, which is safe for threads and
async coroutines.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass, field
from typing import Any

from .config import FrameworkConfig
from .engine import EventEngine
from .portfolio import Portfolio
from .risk import RiskManager

_current_context: contextvars.ContextVar[Context | None] = contextvars.ContextVar(
    "current_context",
    default=None,
)


@dataclass(slots=True)
class Context:
    """Runtime context passed through framework components.

    Attributes:
        config: Framework configuration object.
        portfolio: Portfolio manager instance.
        risk_manager: Risk manager instance.
        event_engine: Event engine instance.
        logger: Logger used by strategy/framework runtime.
        data: Mutable custom storage for user-defined context values.
    """

    config: FrameworkConfig
    portfolio: Portfolio
    risk_manager: RiskManager
    event_engine: EventEngine
    logger: logging.Logger
    data: dict[str, Any] = field(default_factory=dict)
    _tokens: list[contextvars.Token[Context | None]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def get(self, key: str, default: Any = None) -> Any:
        """Get custom value from context data.

        Args:
            key: Data key.
            default: Value to return when key is missing.

        Returns:
            Stored value or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set custom value into context data.

        Args:
            key: Data key.
            value: Value to store.
        """
        self.data[key] = value

    def __enter__(self) -> Context:
        """Set this context as current and return itself."""
        token = _current_context.set(self)
        self._tokens.append(token)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Restore previous current context when leaving ``with`` block."""
        _ = (exc_type, exc, tb)
        token = self._tokens.pop()
        _current_context.reset(token)


def get_current_context() -> Context | None:
    """Get current runtime context for this execution flow."""
    return _current_context.get()


def set_current_context(ctx: Context | None) -> None:
    """Set current runtime context for this execution flow.

    Args:
        ctx: Context instance to set, or ``None`` to clear.
    """
    _current_context.set(ctx)
