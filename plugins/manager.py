"""Plugin manager implementation.

This module provides plugin registry, dependency resolution, lifecycle
management, and hook dispatching for framework plugins.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from core.context import Context

from .base import Plugin


class PluginManager:
    """Manage plugin registration, lifecycle, dependency and hook calls."""

    def __init__(self) -> None:
        """Initialize an empty plugin manager."""
        self._plugins: dict[str, Plugin] = {}
        self._initialized: bool = False
        self._init_order: list[str] = []

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: Plugin instance to register.

        Raises:
            ValueError: If a plugin with the same name is already registered.
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        """Unregister plugin by name.

        Args:
            name: Plugin name.
        """
        self._plugins.pop(name, None)

    def get(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        return self._plugins.get(name)

    def get_all(self) -> list[Plugin]:
        """Return all registered plugins in registration order."""
        return list(self._plugins.values())

    def has(self, name: str) -> bool:
        """Return whether a plugin is registered."""
        return name in self._plugins

    def initialize(self, context: Context) -> None:
        """Initialize all plugins by dependency order.

        Args:
            context: Runtime context.
        """
        if self._initialized:
            return

        self._check_dependencies()
        self._detect_cycles()

        order = self._resolve_order()
        for name in order:
            self._plugins[name].setup(context)

        self._init_order = order
        self._initialized = True

    def shutdown(self, context: Context) -> None:
        """Shutdown initialized plugins in reverse initialization order.

        Args:
            context: Runtime context.
        """
        if not self._initialized:
            return

        for name in reversed(self._init_order):
            self._plugins[name].teardown(context)

        self._initialized = False
        self._init_order = []

    def _resolve_order(self) -> list[str]:
        """Resolve plugin initialization order using topological sort."""
        graph: dict[str, list[str]] = {name: [] for name in self._plugins}
        indegree: dict[str, int] = {name: 0 for name in self._plugins}

        for plugin_name, plugin in self._plugins.items():
            for dependency in plugin.dependencies:
                graph[dependency].append(plugin_name)
                indegree[plugin_name] += 1

        queue: deque[str] = deque(name for name in self._plugins if indegree[name] == 0)
        order: list[str] = []

        while queue:
            current = queue.popleft()
            order.append(current)

            for neighbor in graph[current]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._plugins):
            raise ValueError("Dependency cycle detected")

        return order

    def _check_dependencies(self) -> None:
        """Validate all plugin dependencies are registered."""
        for plugin in self._plugins.values():
            for dependency in plugin.dependencies:
                if dependency not in self._plugins:
                    raise ValueError(
                        f"Missing dependency for '{plugin.name}': '{dependency}'"
                    )

    def _detect_cycles(self) -> None:
        """Detect circular dependencies.

        Raises:
            ValueError: If a dependency cycle is found.
        """
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(name: str) -> None:
            if name in visiting:
                raise ValueError("Dependency cycle detected")
            if name in visited:
                return

            visiting.add(name)
            plugin = self._plugins[name]
            for dep in plugin.dependencies:
                dfs(dep)
            visiting.remove(name)
            visited.add(name)

        for name in self._plugins:
            if name not in visited:
                dfs(name)

    def call_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Call the named hook on every plugin and collect results.

        Args:
            hook_name: Hook method name.
            *args: Positional hook arguments.
            **kwargs: Keyword hook arguments.

        Returns:
            Hook return values from plugins that implement the hook.
        """
        results: list[Any] = []

        for plugin in self._plugins.values():
            hook = getattr(plugin, hook_name, None)
            if callable(hook):
                results.append(hook(*args, **kwargs))

        return results
