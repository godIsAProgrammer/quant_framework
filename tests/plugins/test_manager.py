"""Unit tests for plugin manager (Day 7, TDD)."""

from __future__ import annotations

import logging

import pytest

from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager
from plugins.base import Plugin
from plugins.manager import PluginManager


def _build_context() -> Context:
    return Context(
        config=FrameworkConfig(),
        portfolio=Portfolio(initial_cash=100_000),
        risk_manager=RiskManager(),
        event_engine=EventEngine(),
        logger=logging.getLogger("test.plugins.manager"),
    )


class _TrackedPlugin(Plugin):
    """Plugin test double that tracks setup/teardown/hook calls."""

    def __init__(
        self,
        name: str,
        *,
        dependencies: list[str] | None = None,
        events: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.dependencies = dependencies or []
        self._events = events if events is not None else []

    def setup(self, context: Context) -> None:
        _ = context
        self._events.append(f"setup:{self.name}")

    def teardown(self, context: Context) -> None:
        _ = context
        self._events.append(f"teardown:{self.name}")

    def on_bar(self, value: int) -> str:
        return f"{self.name}:{value}"


def test_register_plugin() -> None:
    """PluginManager should register plugin instances by name."""
    manager = PluginManager()
    plugin = _TrackedPlugin("alpha")

    manager.register(plugin)

    assert manager.has("alpha") is True
    assert manager.get("alpha") is plugin


def test_unregister_plugin() -> None:
    """PluginManager should remove plugin by name."""
    manager = PluginManager()
    plugin = _TrackedPlugin("alpha")
    manager.register(plugin)

    manager.unregister("alpha")

    assert manager.has("alpha") is False
    assert manager.get("alpha") is None


def test_get_plugin_by_name() -> None:
    """PluginManager.get should return plugin by exact name."""
    manager = PluginManager()
    alpha = _TrackedPlugin("alpha")
    beta = _TrackedPlugin("beta")
    manager.register(alpha)
    manager.register(beta)

    assert manager.get("alpha") is alpha
    assert manager.get("beta") is beta
    assert manager.get("missing") is None


def test_get_all_plugins() -> None:
    """PluginManager.get_all should return all registered plugins."""
    manager = PluginManager()
    alpha = _TrackedPlugin("alpha")
    beta = _TrackedPlugin("beta")
    manager.register(alpha)
    manager.register(beta)

    plugins = manager.get_all()

    assert plugins == [alpha, beta]


def test_initialize_calls_setup() -> None:
    """PluginManager.initialize should call setup for each plugin."""
    events: list[str] = []
    manager = PluginManager()
    manager.register(_TrackedPlugin("alpha", events=events))
    manager.register(_TrackedPlugin("beta", events=events))

    manager.initialize(_build_context())

    assert events == ["setup:alpha", "setup:beta"]


def test_shutdown_calls_teardown_in_reverse_order() -> None:
    """PluginManager.shutdown should call teardown in reverse init order."""
    events: list[str] = []
    manager = PluginManager()
    manager.register(_TrackedPlugin("alpha", events=events))
    manager.register(_TrackedPlugin("beta", events=events))

    ctx = _build_context()
    manager.initialize(ctx)
    manager.shutdown(ctx)

    assert events == [
        "setup:alpha",
        "setup:beta",
        "teardown:beta",
        "teardown:alpha",
    ]


def test_dependency_resolution_initializes_in_topological_order() -> None:
    """PluginManager should initialize plugins after their dependencies."""
    events: list[str] = []
    manager = PluginManager()

    manager.register(_TrackedPlugin("strategy", dependencies=["data"], events=events))
    manager.register(_TrackedPlugin("data", events=events))

    manager.initialize(_build_context())

    assert events == ["setup:data", "setup:strategy"]


def test_cycle_dependency_detection() -> None:
    """PluginManager should raise when circular dependencies exist."""
    manager = PluginManager()
    manager.register(_TrackedPlugin("a", dependencies=["b"]))
    manager.register(_TrackedPlugin("b", dependencies=["a"]))

    with pytest.raises(ValueError, match="cycle"):
        manager.initialize(_build_context())


def test_missing_dependency_detection() -> None:
    """PluginManager should raise when a dependency is not registered."""
    manager = PluginManager()
    manager.register(_TrackedPlugin("strategy", dependencies=["data"]))

    with pytest.raises(ValueError, match="Missing dependency"):
        manager.initialize(_build_context())


def test_call_hook_dispatches_to_all_plugins() -> None:
    """PluginManager.call_hook should dispatch hook calls and collect results."""
    manager = PluginManager()
    manager.register(_TrackedPlugin("alpha"))
    manager.register(_TrackedPlugin("beta"))

    results = manager.call_hook("on_bar", 42)

    assert results == ["alpha:42", "beta:42"]
