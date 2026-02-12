"""Unit tests for plugin hook specifications and callers (Day 6, TDD)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from plugins.hookspecs import HookCaller, hookimpl, hookspec
from plugins.specs import QuantHookSpec


@dataclass(slots=True)
class DummyContext:
    """Simple context object for hook tests."""

    name: str = "ctx"


def test_hookspec_decorator_marks_function() -> None:
    """hookspec should mark a function as hook specification."""

    @hookspec
    def on_event(context: DummyContext) -> None:
        return None

    assert getattr(on_event, "__hookspec__", False) is True
    opts = getattr(on_event, "__hookspec_opts__")
    assert opts["first_result"] is False
    assert opts["optional"] is False


def test_hookimpl_decorator_marks_function() -> None:
    """hookimpl should mark a function as hook implementation."""

    @hookimpl(priority=7)
    def impl(context: DummyContext) -> str:
        return context.name

    assert getattr(impl, "__hookimpl__", False) is True
    opts = getattr(impl, "__hookimpl_opts__")
    assert opts["priority"] == 7


def test_hookcaller_calls_registered_implementation() -> None:
    """HookCaller should invoke registered implementations."""

    caller = HookCaller(name="on_start")

    @hookimpl
    def on_start(context: DummyContext) -> str:
        return f"started:{context.name}"

    caller.register(on_start)

    result = caller.call(DummyContext("alpha"))

    assert result == ["started:alpha"]


def test_hookcaller_first_result_returns_first_non_none() -> None:
    """first_result mode should return first non-None result."""

    caller = HookCaller(name="on_order", first_result=True)

    @hookimpl(priority=20)
    def impl_high(_context: DummyContext, _order: dict[str, int]) -> None:
        return None

    @hookimpl(priority=10)
    def impl_mid(_context: DummyContext, order: dict[str, int]) -> dict[str, int]:
        return {"value": order["value"] + 1}

    @hookimpl(priority=1)
    def impl_low(_context: DummyContext, order: dict[str, int]) -> dict[str, int]:
        return {"value": order["value"] + 100}

    caller.register(impl_low)
    caller.register(impl_mid)
    caller.register(impl_high)

    result = caller.call(DummyContext(), {"value": 1})

    assert result == {"value": 2}


def test_hookcaller_all_results_collects_all_values() -> None:
    """all_results mode should collect all implementation return values."""

    caller = HookCaller(name="on_trade", first_result=False)

    @hookimpl(priority=2)
    def impl_a(_context: DummyContext, _trade: dict[str, int]) -> str:
        return "A"

    @hookimpl(priority=1)
    def impl_b(_context: DummyContext, _trade: dict[str, int]) -> str:
        return "B"

    caller.register(impl_b)
    caller.register(impl_a)

    result = caller.call(DummyContext(), {"id": 1})

    assert result == ["A", "B"]


def test_hookcaller_passes_args_and_kwargs_to_implementation() -> None:
    """HookCaller should pass *args and **kwargs to each implementation."""

    caller = HookCaller(name="on_bar")

    received: list[tuple[str, dict[str, int], str]] = []

    @hookimpl
    def impl(context: DummyContext, bar: dict[str, int], source: str = "") -> str:
        received.append((context.name, bar, source))
        return "ok"

    caller.register(impl)

    result = caller.call(DummyContext("beta"), {"close": 123}, source="feed")

    assert result == ["ok"]
    assert received == [("beta", {"close": 123}, "feed")]


def test_hookcaller_optional_hook_without_impl_does_not_raise() -> None:
    """Optional hooks should not raise when there are no implementations."""

    all_results_caller = HookCaller(name="on_optional", optional=True)
    first_result_caller = HookCaller(
        name="on_optional_first",
        first_result=True,
        optional=True,
    )

    assert all_results_caller.call(DummyContext()) == []
    assert first_result_caller.call(DummyContext()) is None


def test_hookcaller_non_optional_hook_without_impl_raises() -> None:
    """Non-optional hooks should raise when no implementation is registered."""

    caller = HookCaller(name="on_required", optional=False)

    with pytest.raises(LookupError):
        caller.call(DummyContext())


def test_quant_hookspec_builtin_hooks_are_marked() -> None:
    """Built-in QuantHookSpec methods should all be marked as hookspec."""

    method_names = [
        "on_init",
        "on_start",
        "on_stop",
        "on_bar",
        "on_order",
        "on_trade",
        "on_error",
    ]

    for method_name in method_names:
        method = getattr(QuantHookSpec, method_name)
        assert getattr(method, "__hookspec__", False) is True

    order_opts = getattr(QuantHookSpec.on_order, "__hookspec_opts__")
    error_opts = getattr(QuantHookSpec.on_error, "__hookspec_opts__")

    assert order_opts["first_result"] is True
    assert error_opts["optional"] is True


def test_hookcaller_executes_by_priority_descending() -> None:
    """Hook implementations should run from higher priority to lower priority."""

    caller = HookCaller(name="on_priority")
    order: list[str] = []

    @hookimpl(priority=1)
    def low(_context: DummyContext) -> str:
        order.append("low")
        return "low"

    @hookimpl(priority=100)
    def high(_context: DummyContext) -> str:
        order.append("high")
        return "high"

    @hookimpl(priority=50)
    def mid(_context: DummyContext) -> str:
        order.append("mid")
        return "mid"

    caller.register(low)
    caller.register(high)
    caller.register(mid)

    result = caller.call(DummyContext())

    assert order == ["high", "mid", "low"]
    assert result == ["high", "mid", "low"]
