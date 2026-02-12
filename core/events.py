"""Event model and event type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Supported event types in the framework."""

    TICK = "TICK"
    BAR = "BAR"
    ORDER = "ORDER"
    TRADE = "TRADE"
    POSITION = "POSITION"
    SIGNAL = "SIGNAL"
    RISK = "RISK"
    LOG = "LOG"
    ERROR = "ERROR"
    START = "START"
    STOP = "STOP"
    HEARTBEAT = "HEARTBEAT"


@dataclass(slots=True)
class Event:
    """Base event object passed through the event engine."""

    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Convenient aliases for readability.
TICK = EventType.TICK
BAR = EventType.BAR
ORDER = EventType.ORDER
TRADE = EventType.TRADE
POSITION = EventType.POSITION
SIGNAL = EventType.SIGNAL
RISK = EventType.RISK
LOG = EventType.LOG
ERROR = EventType.ERROR
START = EventType.START
STOP = EventType.STOP
HEARTBEAT = EventType.HEARTBEAT
