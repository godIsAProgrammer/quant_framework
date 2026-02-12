"""Plugin base class definitions.

This module defines the default plugin lifecycle and shared metadata fields.
"""

from __future__ import annotations

from core.context import Context


class Plugin:
    """Base class for all framework plugins.

    Subclasses can override metadata fields and lifecycle hooks.
    """

    name: str = "plugin"
    version: str = "0.1.0"
    description: str = ""
    dependencies: list[str] = []

    def __init__(self) -> None:
        """Initialize plugin state."""
        self.enabled = True
        self.dependencies = list(self.__class__.dependencies)

    def setup(self, context: Context) -> None:
        """Run initialization lifecycle hook."""
        _ = context

    def teardown(self, context: Context) -> None:
        """Run cleanup lifecycle hook."""
        _ = context

    def enable(self) -> None:
        """Enable this plugin."""
        self.enabled = True

    def disable(self) -> None:
        """Disable this plugin."""
        self.enabled = False
