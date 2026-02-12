"""Hook specification and implementation utilities.

This module provides lightweight hook decorators and a caller that executes
registered implementations in priority order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class HookSpecOptions:
    """Options attached to a hook specification."""

    first_result: bool = False
    optional: bool = False


@dataclass(frozen=True, slots=True)
class HookImplOptions:
    """Options attached to a hook implementation."""

    priority: int = 0


def hookspec(
    func: Callable[P, R] | None = None,
    *,
    first_result: bool = False,
    optional: bool = False,
) -> Any:
    """Mark a function as a hook specification.

    Args:
        func: Function to decorate when used as ``@hookspec``.
        first_result: Whether callers should stop at first non-``None`` result.
        optional: Whether missing implementations are allowed.

    Returns:
        Decorated function, or a decorator when used with keyword arguments.
    """

    def decorator(target: Callable[P, R]) -> Callable[P, R]:
        setattr(target, "__hookspec__", True)
        setattr(
            target,
            "__hookspec_opts__",
            {
                "first_result": first_result,
                "optional": optional,
            },
        )
        return target

    if func is None:
        return decorator
    return decorator(func)


def hookimpl(
    func: Callable[P, R] | None = None,
    *,
    priority: int = 0,
) -> Any:
    """Mark a function as a hook implementation.

    Args:
        func: Function to decorate when used as ``@hookimpl``.
        priority: Implementation priority. Higher values run earlier.

    Returns:
        Decorated function, or a decorator when used with keyword arguments.
    """

    def decorator(target: Callable[P, R]) -> Callable[P, R]:
        setattr(target, "__hookimpl__", True)
        setattr(target, "__hookimpl_opts__", {"priority": priority})
        return target

    if func is None:
        return decorator
    return decorator(func)


@dataclass(slots=True)
class _RegisteredHookImpl:
    """Internal registered hook implementation entry."""

    func: Callable[..., Any]
    priority: int


class HookCaller:
    """Execute hook implementations for one hook name.

    Implementations are sorted by descending priority.
    """

    def __init__(
        self,
        *,
        name: str,
        first_result: bool = False,
        optional: bool = False,
    ) -> None:
        self.name = name
        self.first_result = first_result
        self.optional = optional
        self._implementations: list[_RegisteredHookImpl] = []

    def register(self, func: Callable[..., Any]) -> None:
        """Register one hook implementation function."""
        opts = cast(dict[str, Any], getattr(func, "__hookimpl_opts__", {}))
        priority = int(opts.get("priority", 0))
        self._implementations.append(_RegisteredHookImpl(func=func, priority=priority))
        self._implementations.sort(key=lambda impl: impl.priority, reverse=True)

    def call(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke all registered implementations according to caller mode."""
        if not self._implementations:
            if self.optional:
                return None if self.first_result else []
            raise LookupError(f"No hook implementations registered for '{self.name}'")

        if self.first_result:
            for impl in self._implementations:
                result = impl.func(*args, **kwargs)
                if result is not None:
                    return result
            return None

        results: list[Any] = []
        for impl in self._implementations:
            results.append(impl.func(*args, **kwargs))
        return results
