"""
EventEngine 单元测试
"""

import pytest
from unittest.mock import Mock, call

from core.engine import Event, EventEngine, EventType, create_engine


class TestEvent:
    """测试Event类"""
    
    def test_event_creation(self):
        """测试事件创建"""
        event = Event(EventType.BAR, data={"symbol": "000001"})
        assert event.type == EventType.BAR
        assert event.data == {"symbol": "000001"}
        assert event.timestamp is not None
        assert event.source is None
    
    def test_event_with_source(self):
        """测试带source的事件"""
        event = Event(EventType.TICK, data={}, source="test")
        assert event.source == "test"


class TestEventEngine:
    """测试EventEngine类"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.engine = EventEngine()
    
    def test_engine_initialization(self):
        """测试引擎初始化"""
        assert not self.engine.is_running()
        stats = self.engine.get_stats()
        assert stats["running"] is False
        assert stats["event_count"] == 0
        assert stats["error_count"] == 0
    
    def test_start_stop(self):
        """测试启动和停止"""
        self.engine.start()
        assert self.engine.is_running()
        
        self.engine.stop()
        assert not self.engine.is_running()
    
    def test_register_handler(self):
        """测试注册处理器"""
        handler = Mock()
        self.engine.register(EventType.BAR, handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR, data="test"))
        self.engine.stop()
        
        handler.assert_called_once()
    
    def test_register_with_priority(self):
        """测试带优先级的注册"""
        results = []
        
        def handler_low(event):
            results.append("low")
        
        def handler_high(event):
            results.append("high")
        
        self.engine.register(EventType.BAR, handler_low, priority=1)
        self.engine.register(EventType.BAR, handler_high, priority=10)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR))
        self.engine.stop()
        
        # 高优先级应该先执行
        assert results == ["high", "low"]
    
    def test_decorator_registration(self):
        """测试装饰器注册"""
        results = []
        
        @self.engine.on(EventType.BAR, priority=5)
        def on_bar(event):
            results.append(event.data)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR, data="test_data"))
        self.engine.stop()
        
        assert results == ["test_data"]
    
    def test_unregister_handler(self):
        """测试注销处理器"""
        handler = Mock()
        self.engine.register(EventType.BAR, handler)
        
        # 注销成功
        assert self.engine.unregister(EventType.BAR, handler) is True
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR))
        self.engine.stop()
        
        # 处理器不应被调用
        handler.assert_not_called()
    
    def test_unregister_not_exist(self):
        """测试注销不存在的处理器"""
        handler = Mock()
        assert self.engine.unregister(EventType.BAR, handler) is False
    
    def test_multiple_handlers(self):
        """测试多个处理器"""
        results = []
        
        def handler1(event):
            results.append(1)
        
        def handler2(event):
            results.append(2)
        
        self.engine.register(EventType.BAR, handler1)
        self.engine.register(EventType.BAR, handler2)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR))
        self.engine.stop()
        
        assert sorted(results) == [1, 2]
    
    def test_different_event_types(self):
        """测试不同事件类型"""
        bar_handler = Mock()
        tick_handler = Mock()
        
        self.engine.register(EventType.BAR, bar_handler)
        self.engine.register(EventType.TICK, tick_handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR, data="bar"))
        self.engine.put(Event(EventType.TICK, data="tick"))
        self.engine.stop()
        
        bar_handler.assert_called_once()
        tick_handler.assert_called_once()
    
    def test_error_isolation(self):
        """测试错误隔离 - 一个处理器异常不影响其他处理器"""
        results = []
        
        def error_handler(event):
            raise ValueError("Test error")
        
        def normal_handler(event):
            results.append("ok")
        
        self.engine.register(EventType.BAR, error_handler)
        self.engine.register(EventType.BAR, normal_handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR))
        self.engine.stop()
        
        # 正常处理器应该被调用
        assert results == ["ok"]
        
        stats = self.engine.get_stats()
        assert stats["error_count"] == 1
    
    def test_middleware(self):
        """测试中间件"""
        results = []
        
        def middleware(event):
            event.data["modified"] = True
            return event
        
        def handler(event):
            results.append(event.data.get("modified"))
        
        self.engine.use(middleware)
        self.engine.register(EventType.BAR, handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR, data={}))
        self.engine.stop()
        
        assert results == [True]
    
    def test_middleware_filter(self):
        """测试中间件过滤事件"""
        handler = Mock()
        
        def filter_middleware(event):
            if event.data.get("filtered"):
                return None  # 过滤掉
            return event
        
        self.engine.use(filter_middleware)
        self.engine.register(EventType.BAR, handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR, data={"filtered": True}))
        self.engine.put(Event(EventType.BAR, data={"filtered": False}))
        self.engine.stop()
        
        # 只有未被过滤的事件会被处理
        assert handler.call_count == 1
    
    def test_middleware_error(self):
        """测试中间件错误"""
        handler = Mock()
        
        def error_middleware(event):
            raise RuntimeError("Middleware error")
        
        self.engine.use(error_middleware)
        self.engine.register(EventType.BAR, handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.BAR))
        self.engine.stop()
        
        # 中间件错误不应影响后续处理
        handler.assert_called_once()
        
        stats = self.engine.get_stats()
        assert stats["error_count"] == 1
    
    def test_handler_returns_event(self):
        """测试处理器返回新事件"""
        results = []
        
        def signal_handler(event):
            results.append(f"signal: {event.data}")
            return Event(EventType.ORDER, data="new_order")
        
        def order_handler(event):
            results.append(f"order: {event.data}")
        
        self.engine.register(EventType.SIGNAL, signal_handler)
        self.engine.register(EventType.ORDER, order_handler)
        
        self.engine.start()
        self.engine.put(Event(EventType.SIGNAL, data="buy"))
        self.engine.stop()
        
        assert "signal: buy" in results
        assert "order: new_order" in results
    
    def test_put_when_not_running(self):
        """测试引擎未启动时发送事件"""
        handler = Mock()
        self.engine.register(EventType.BAR, handler)
        
        # 不启动引擎直接发送
        self.engine.put(Event(EventType.BAR))
        
        handler.assert_not_called()
    
    def test_stats(self):
        """测试统计信息"""
        self.engine.register(EventType.BAR, lambda e: None)
        self.engine.register(EventType.TICK, lambda e: None)
        self.engine.use(lambda e: e)
        
        stats = self.engine.get_stats()
        assert stats["handlers"]["BAR"] == 1
        assert stats["handlers"]["TICK"] == 1
        assert stats["middlewares"] == 1
    
    def test_register_non_callable(self):
        """测试注册非callable处理器"""
        with pytest.raises(ValueError, match="Handler must be callable"):
            self.engine.register(EventType.BAR, "not_callable")
    
    def test_use_non_callable_middleware(self):
        """测试添加非callable中间件"""
        with pytest.raises(ValueError, match="Middleware must be callable"):
            self.engine.use("not_callable")


class TestCreateEngine:
    """测试create_engine便捷函数"""
    
    def test_create_engine(self):
        """测试创建引擎"""
        engine = create_engine()
        assert isinstance(engine, EventEngine)
        assert not engine.is_running()
