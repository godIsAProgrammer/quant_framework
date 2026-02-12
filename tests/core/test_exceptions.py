"""Unit tests for exception framework (Day 5, TDD)."""

from __future__ import annotations

import pytest

from core.exceptions import (
    ConfigError,
    DataError,
    QuantError,
    RiskError,
    StrategyError,
    TradeError,
    ValidationError,
    format_exception,
    wrap_exception,
)


def test_quant_error_base_fields() -> None:
    """QuantError should keep message/code/context/cause fields."""
    err = QuantError(
        "base failure",
        code="BASE_001",
        context={"module": "engine", "retry": 1},
    )

    assert err.message == "base failure"
    assert err.code == "BASE_001"
    assert err.context == {"module": "engine", "retry": 1}
    assert err.cause is None


def test_config_error_type_and_default_code() -> None:
    """ConfigError should be a QuantError with proper default code."""
    err = ConfigError("invalid config")

    assert isinstance(err, QuantError)
    assert err.code == "CONFIG_ERROR"


def test_data_error_type_and_default_code() -> None:
    """DataError should be a QuantError with proper default code."""
    err = DataError("data source timeout")

    assert isinstance(err, QuantError)
    assert err.code == "DATA_ERROR"


def test_strategy_error_type_and_default_code() -> None:
    """StrategyError should be a QuantError with proper default code."""
    err = StrategyError("signal generation failed")

    assert isinstance(err, QuantError)
    assert err.code == "STRATEGY_ERROR"


def test_risk_error_type_and_default_code() -> None:
    """RiskError should be a QuantError with proper default code."""
    err = RiskError("position limit exceeded")

    assert isinstance(err, QuantError)
    assert err.code == "RISK_ERROR"


def test_trade_error_type_and_default_code() -> None:
    """TradeError should be a QuantError with proper default code."""
    err = TradeError("order rejected")

    assert isinstance(err, QuantError)
    assert err.code == "TRADE_ERROR"


def test_validation_error_type_and_default_code() -> None:
    """ValidationError should be a QuantError with proper default code."""
    err = ValidationError("field validation failed")

    assert isinstance(err, QuantError)
    assert err.code == "VALIDATION_ERROR"


def test_exception_chain_with_cause() -> None:
    """QuantError should keep original cause for chained exceptions."""
    root = ValueError("bad integer")
    err = DataError("parse failed", cause=root)

    assert err.cause is root
    assert err.__cause__ is root


def test_exception_context_information() -> None:
    """format_exception should include context information for QuantError."""
    err = StrategyError(
        "strategy runtime failure",
        context={"strategy": "double_low", "symbol": "000001.SZ"},
    )

    formatted = format_exception(err)

    assert "STRATEGY_ERROR" in formatted
    assert "strategy runtime failure" in formatted
    assert "strategy" in formatted
    assert "double_low" in formatted
    assert "symbol" in formatted


def test_wrap_external_exception() -> None:
    """wrap_exception should wrap external exception into target QuantError type."""
    external = RuntimeError("network disconnected")

    wrapped = wrap_exception(
        external,
        DataError,
        "failed to fetch market data",
    )

    assert isinstance(wrapped, DataError)
    assert wrapped.message == "failed to fetch market data"
    assert wrapped.cause is external
    assert wrapped.__cause__ is external


def test_format_exception_for_generic_exception() -> None:
    """format_exception should gracefully handle built-in exceptions."""
    err = KeyError("api_key")

    formatted = format_exception(err)

    assert "KeyError" in formatted
    assert "api_key" in formatted


def test_wrap_exception_with_custom_code_and_context() -> None:
    """wrap_exception should allow overriding code and attaching context."""
    external = ValueError("raw payload malformed")

    wrapped = wrap_exception(
        external,
        ValidationError,
        "payload validation failed",
        code="VAL_400",
        context={"field": "price", "line": 12},
    )

    assert wrapped.code == "VAL_400"
    assert wrapped.context == {"field": "price", "line": 12}
    assert wrapped.cause is external


def test_quant_error_str_uses_format_exception() -> None:
    """QuantError string should expose formatted information."""
    err = TradeError("trade failed", context={"symbol": "000001.SZ"})

    text = str(err)

    assert "TRADE_ERROR" in text
    assert "trade failed" in text
    assert "symbol" in text
