"""Exception hierarchy and helpers for quant framework.

This module provides a consistent exception model used by core components:

- ``QuantError`` as the base class with error code, context and root cause.
- Domain-specific subclasses for config/data/strategy/risk/trade/validation.
- Utility helpers to wrap external exceptions and to format errors.
"""

from __future__ import annotations

from typing import Any, Mapping, TypeVar

TQuantError = TypeVar("TQuantError", bound="QuantError")


class QuantError(Exception):
    """Base exception for all framework-level errors.

    Attributes:
        message: Human-readable error message.
        code: Stable error code for programmatic processing.
        context: Extra metadata useful for debugging and logging.
        cause: Original exception that triggered this error.
    """

    def __init__(
        self,
        message: str,
        code: str = "QUANT_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.message: str = message
        self.code: str = code
        self.context: dict[str, Any] = dict(context) if context is not None else {}
        self.cause: Exception | None = cause

        super().__init__(message)

        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        """Return a formatted, readable exception string."""
        return format_exception(self)


class ConfigError(QuantError):
    """Configuration related error."""

    def __init__(
        self,
        message: str,
        code: str = "CONFIG_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


class DataError(QuantError):
    """Market data fetching/parsing related error."""

    def __init__(
        self,
        message: str,
        code: str = "DATA_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


class StrategyError(QuantError):
    """Strategy execution related error."""

    def __init__(
        self,
        message: str,
        code: str = "STRATEGY_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


class RiskError(QuantError):
    """Risk-control related error."""

    def __init__(
        self,
        message: str,
        code: str = "RISK_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


class TradeError(QuantError):
    """Trade execution related error."""

    def __init__(
        self,
        message: str,
        code: str = "TRADE_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


class ValidationError(QuantError):
    """Input/data validation related error."""

    def __init__(
        self,
        message: str,
        code: str = "VALIDATION_ERROR",
        context: Mapping[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message=message, code=code, context=context, cause=cause)


def wrap_exception(
    exc: Exception,
    error_class: type[TQuantError],
    message: str,
    *,
    code: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> TQuantError:
    """Wrap an external exception with a framework exception class.

    Args:
        exc: Original exception raised by external dependency or lower layer.
        error_class: Target ``QuantError`` subclass to construct.
        message: Message for the wrapped exception.
        code: Optional explicit error code overriding class default.
        context: Optional context payload.

    Returns:
        An instance of ``error_class`` that chains ``exc`` as its cause.
    """
    kwargs: dict[str, Any] = {"context": context, "cause": exc}
    if code is not None:
        kwargs["code"] = code
    return error_class(message, **kwargs)


def format_exception(exc: BaseException) -> str:
    """Format exception into a readable one-line text.

    For ``QuantError`` it includes code, message, context and cause.
    For generic exceptions, it returns ``<Type>: <message>``.
    """
    if isinstance(exc, QuantError):
        base = f"[{exc.code}] {exc.message}"
        context_part = ""
        if exc.context:
            context_items = ", ".join(
                f"{key}={value!r}" for key, value in sorted(exc.context.items())
            )
            context_part = f" | context: {context_items}"

        cause_part = ""
        if exc.cause is not None:
            cause_part = f" | cause: {type(exc.cause).__name__}: {exc.cause}"

        return f"{base}{context_part}{cause_part}"

    return f"{type(exc).__name__}: {exc}"


__all__ = [
    "QuantError",
    "ConfigError",
    "DataError",
    "StrategyError",
    "RiskError",
    "TradeError",
    "ValidationError",
    "wrap_exception",
    "format_exception",
]
