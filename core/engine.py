"""
QuantCore - EventEngine 事件引擎

核心设计:
- 支持同步/异步事件分发
- 中间件链式处理
- 错误隔离（单处理器异常不影响其他处理器）
- 优先级支持
"""

from __future__ import annotations

import logging
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar, Union

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    # 行情事件
    BAR = auto()           # K线数据
    TICK = auto()          #  tick数据
    QUOTE = auto()         # 报价
    
    # 交易事件
    ORDER = auto()         # 订单
    TRADE = auto()         # 成交
    POSITION = auto()      # 持仓变化
    
    # 系统事件
    START = auto()         # 引擎启动
    STOP = auto()          # 引擎停止
    ERROR = auto()         # 错误
    
    # 风控事件
    RISK_CHECK = auto()    # 风控检查
    RISK_TRIGGER = auto()  # 风控触发
    
    # 策略事件
    SIGNAL = auto()        # 策略信号
    STRATEGY_INIT = auto() # 策略初始化
    STRATEGY_STOP = auto() # 策略停止


@dataclass
class Event:
    """事件对象"""
    type: EventType
    data: Any = None
    timestamp: Optional[float] = None
    source: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


# 处理器类型
Handler = Callable[[Event], Optional[Event]]
Middleware = Callable[[Event], Optional[Event]]


@dataclass
class HandlerInfo:
    """处理器信息"""
    handler: Handler
    priority: int = 0  # 数值越大优先级越高
    
    def __lt__(self, other: HandlerInfo) -> bool:
        return self.priority < other.priority


class EventEngine:
    """
    事件引擎
    
    核心功能:
    1. 事件注册/注销
    2. 事件分发（支持优先级）
    3. 中间件链式处理
    4. 错误隔离
    
    使用示例:
        engine = EventEngine()
        
        @engine.on(EventType.BAR)
        def on_bar(event: Event):
            print(f"收到K线: {event.data}")
        
        engine.start()
        engine.put(Event(EventType.BAR, data={"symbol": "000001", "close": 10.5}))
        engine.stop()
    """
    
    def __init__(self):
        """初始化事件引擎"""
        self._handlers: Dict[EventType, List[HandlerInfo]] = defaultdict(list)
        self._middlewares: List[Middleware] = []
        self._running = False
        self._event_count = 0
        self._error_count = 0
        
        logger.info("EventEngine initialized")
    
    def on(self, event_type: EventType, priority: int = 0) -> Callable:
        """
        事件注册装饰器
        
        Args:
            event_type: 事件类型
            priority: 优先级，数值越大越先执行
            
        Returns:
            装饰器函数
            
        Example:
            @engine.on(EventType.BAR, priority=10)
            def on_bar(event):
                print(event.data)
        """
        def decorator(handler: Handler) -> Handler:
            self.register(event_type, handler, priority)
            return handler
        return decorator
    
    def register(
        self, 
        event_type: EventType, 
        handler: Handler, 
        priority: int = 0
    ) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理器函数
            priority: 优先级
        """
        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")
        
        handler_info = HandlerInfo(handler=handler, priority=priority)
        self._handlers[event_type].append(handler_info)
        # 按优先级排序
        self._handlers[event_type].sort(reverse=True)
        
        logger.debug(f"Registered handler for {event_type.name} with priority {priority}")
    
    def unregister(self, event_type: EventType, handler: Handler) -> bool:
        """
        注销事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理器函数
            
        Returns:
            是否成功注销
        """
        handlers = self._handlers.get(event_type, [])
        for i, info in enumerate(handlers):
            if info.handler == handler:
                handlers.pop(i)
                logger.debug(f"Unregistered handler for {event_type.name}")
                return True
        return False
    
    def use(self, middleware: Middleware) -> None:
        """
        添加中间件
        
        中间件可以对事件进行预处理、过滤或转换。
        如果中间件返回None，事件不会继续传递给处理器。
        
        Args:
            middleware: 中间件函数
            
        Example:
            def log_middleware(event):
                print(f"Event: {event.type}")
                return event
            
            engine.use(log_middleware)
        """
        if not callable(middleware):
            raise ValueError(f"Middleware must be callable, got {type(middleware)}")
        
        self._middlewares.append(middleware)
        logger.debug(f"Added middleware, total: {len(self._middlewares)}")
    
    def put(self, event: Event) -> None:
        """
        发送事件
        
        Args:
            event: 事件对象
        """
        if not self._running:
            logger.warning(f"EventEngine not running, event {event.type.name} dropped")
            return
        
        self._event_count += 1
        
        # 中间件处理
        current_event = event
        for middleware in self._middlewares:
            try:
                current_event = middleware(current_event)
                if current_event is None:
                    # 中间件返回None，停止传播
                    logger.debug(f"Event {event.type.name} filtered by middleware")
                    return
            except Exception as e:
                logger.error(f"Middleware error: {e}")
                self._error_count += 1
                continue
        
        # 分发给处理器
        handlers = self._handlers.get(current_event.type, [])
        for info in handlers:
            try:
                result = info.handler(current_event)
                # 处理器可以返回新事件，继续传播
                if result is not None and result is not current_event:
                    self.put(result)
            except Exception as e:
                # 错误隔离：单个处理器异常不影响其他处理器
                self._error_count += 1
                logger.error(
                    f"Handler error for {current_event.type.name}: {e}\n"
                    f"{traceback.format_exc()}"
                )
                continue
    
    def start(self) -> None:
        """启动事件引擎"""
        self._running = True
        self._event_count = 0
        self._error_count = 0
        
        # 发送启动事件
        self.put(Event(EventType.START, source="EventEngine"))
        logger.info("EventEngine started")
    
    def stop(self) -> None:
        """停止事件引擎"""
        # 发送停止事件
        self.put(Event(EventType.STOP, source="EventEngine"))
        
        self._running = False
        logger.info(
            f"EventEngine stopped. "
            f"Total events: {self._event_count}, "
            f"Errors: {self._error_count}"
        )
    
    def is_running(self) -> bool:
        """是否运行中"""
        return self._running
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "running": self._running,
            "event_count": self._event_count,
            "error_count": self._error_count,
            "handlers": {
                event_type.name: len(handlers)
                for event_type, handlers in self._handlers.items()
            },
            "middlewares": len(self._middlewares),
        }


# 便捷函数
def create_engine() -> EventEngine:
    """创建事件引擎实例"""
    return EventEngine()
