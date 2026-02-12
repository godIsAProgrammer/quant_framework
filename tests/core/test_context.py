"""Unit tests for context management module (Day 5, TDD)."""

from __future__ import annotations

import contextvars
import logging

import pytest

from core.config import FrameworkConfig
from core.context import Context, get_current_context, set_current_context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager


def _build_components() -> tuple[
    FrameworkConfig,
    Portfolio,
    RiskManager,
    EventEngine,
    logging.Logger,
]:
    config = FrameworkConfig()
    portfolio = Portfolio(initial_cash=100_000)
    risk_manager = RiskManager()
    event_engine = EventEngine()
    logger = logging.getLogger("test.context")
    return config, portfolio, risk_manager, event_engine, logger


def test_create_context() -> None:
    """Context can be created with required components."""
    config, portfolio, risk_manager, event_engine, logger = _build_components()

    ctx = Context(
        config=config,
        portfolio=portfolio,
        risk_manager=risk_manager,
        event_engine=event_engine,
        logger=logger,
    )

    assert isinstance(ctx.data, dict)
    assert ctx.data == {}


def test_context_attribute_access() -> None:
    """Context exposes component attributes for direct access."""
    config, portfolio, risk_manager, event_engine, logger = _build_components()

    ctx = Context(
        config=config,
        portfolio=portfolio,
        risk_manager=risk_manager,
        event_engine=event_engine,
        logger=logger,
    )

    assert ctx.config is config
    assert ctx.portfolio is portfolio
    assert ctx.risk_manager is risk_manager
    assert ctx.event_engine is event_engine
    assert ctx.logger is logger


def test_context_nested_propagation() -> None:
    """Nested context managers should correctly restore parent context."""
    outer = Context(*_build_components())
    inner = Context(*_build_components())

    assert get_current_context() is None

    with outer:
        assert get_current_context() is outer
        with inner:
            assert get_current_context() is inner
        assert get_current_context() is outer

    assert get_current_context() is None


def test_context_isolation_between_logical_flows() -> None:
    """Different logical flows should keep independent current contexts."""
    context_a = Context(*_build_components())
    context_b = Context(*_build_components())

    flow_a = contextvars.copy_context()
    flow_b = contextvars.copy_context()

    flow_a.run(set_current_context, context_a)
    flow_b.run(set_current_context, context_b)

    assert flow_a.run(get_current_context) is context_a
    assert flow_b.run(get_current_context) is context_b
    assert get_current_context() is None


def test_context_lifecycle_enter_exit_with_exception() -> None:
    """Context manager should clean up current context on exit, even on errors."""
    ctx = Context(*_build_components())

    with pytest.raises(RuntimeError):
        with ctx:
            assert get_current_context() is ctx
            raise RuntimeError("boom")

    assert get_current_context() is None


def test_context_provides_core_components() -> None:
    """Context should provide access to portfolio/risk_manager/event_engine."""
    ctx = Context(*_build_components())

    assert isinstance(ctx.portfolio, Portfolio)
    assert isinstance(ctx.risk_manager, RiskManager)
    assert isinstance(ctx.event_engine, EventEngine)


def test_get_current_context() -> None:
    """get_current_context should return value set by set_current_context."""
    ctx = Context(*_build_components())

    assert get_current_context() is None

    set_current_context(ctx)
    assert get_current_context() is ctx

    set_current_context(None)
    assert get_current_context() is None


def test_context_data_get_set() -> None:
    """Context data should support custom key-value read/write operations."""
    ctx = Context(*_build_components())

    assert ctx.get("missing") is None
    assert ctx.get("missing", 123) == 123

    ctx.set("alpha", "beta")
    ctx.set("count", 7)

    assert ctx.get("alpha") == "beta"
    assert ctx.get("count") == 7
