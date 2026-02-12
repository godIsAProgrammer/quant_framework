"""
QuantCore - 轻量级插件化量化交易框架
"""

__version__ = "0.1.0"
__author__ = "Quant Team"

from core.engine import Event, EventEngine, EventType, create_engine

__all__ = [
    "Event",
    "EventEngine", 
    "EventType",
    "create_engine",
]
