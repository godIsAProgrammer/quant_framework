#!/usr/bin/env python3
"""
简单测试脚本 - 验证EventEngine核心功能
"""

import sys
sys.path.insert(0, '/Users/caoqiye/.openclaw/workspace-main/quant_framework')

from core.engine import Event, EventEngine, EventType, create_engine


def test_basic():
    """基础功能测试"""
    print("=" * 50)
    print("Test 1: 基础功能测试")
    print("=" * 50)
    
    engine = create_engine()
    results = []
    
    @engine.on(EventType.BAR, priority=10)
    def on_bar_high(event):
        results.append(f"high: {event.data}")
    
    @engine.on(EventType.BAR, priority=1)
    def on_bar_low(event):
        results.append(f"low: {event.data}")
    
    engine.start()
    engine.put(Event(EventType.BAR, data="test"))
    engine.stop()
    
    print(f"Results: {results}")
    assert results == ["high: test", "low: test"], "Priority test failed"
    print("✅ Priority test passed")
    

def test_error_isolation():
    """错误隔离测试"""
    print("\n" + "=" * 50)
    print("Test 2: 错误隔离测试")
    print("=" * 50)
    
    engine = create_engine()
    results = []
    
    def error_handler(event):
        raise ValueError("Test error")
    
    def normal_handler(event):
        results.append("ok")
    
    engine.register(EventType.BAR, error_handler)
    engine.register(EventType.BAR, normal_handler)
    
    engine.start()
    engine.put(Event(EventType.BAR))
    engine.stop()
    
    stats = engine.get_stats()
    print(f"Results: {results}")
    print(f"Stats: {stats}")
    assert results == ["ok"], "Error isolation test failed"
    assert stats['error_count'] == 1, "Error count incorrect"
    print("✅ Error isolation test passed")


def test_middleware():
    """中间件测试"""
    print("\n" + "=" * 50)
    print("Test 3: 中间件测试")
    print("=" * 50)
    
    engine = create_engine()
    results = []
    
    def log_middleware(event):
        print(f"  [Middleware] Processing {event.type.name}")
        return event
    
    def filter_middleware(event):
        if event.data.get("filter"):
            print(f"  [Middleware] Filtered event")
            return None
        return event
    
    @engine.on(EventType.BAR)
    def on_bar(event):
        results.append(event.data.get("value"))
    
    engine.use(log_middleware)
    engine.use(filter_middleware)
    
    engine.start()
    engine.put(Event(EventType.BAR, data={"filter": True, "value": 1}))
    engine.put(Event(EventType.BAR, data={"filter": False, "value": 2}))
    engine.stop()
    
    print(f"Results: {results}")
    assert results == [2], "Middleware filter test failed"
    print("✅ Middleware test passed")


def test_event_propagation():
    """事件传播测试"""
    print("\n" + "=" * 50)
    print("Test 4: 事件传播测试")
    print("=" * 50)
    
    engine = create_engine()
    results = []
    
    @engine.on(EventType.SIGNAL)
    def on_signal(event):
        results.append(f"signal: {event.data}")
        return Event(EventType.ORDER, data="new_order")
    
    @engine.on(EventType.ORDER)
    def on_order(event):
        results.append(f"order: {event.data}")
    
    engine.start()
    engine.put(Event(EventType.SIGNAL, data="buy"))
    engine.stop()
    
    print(f"Results: {results}")
    assert "signal: buy" in results, "Signal handler not called"
    assert "order: new_order" in results, "Order handler not called"
    print("✅ Event propagation test passed")


def test_stats():
    """统计信息测试"""
    print("\n" + "=" * 50)
    print("Test 5: 统计信息测试")
    print("=" * 50)
    
    engine = create_engine()
    
    engine.register(EventType.BAR, lambda e: None)
    engine.register(EventType.TICK, lambda e: None)
    engine.use(lambda e: e)
    
    stats = engine.get_stats()
    print(f"Stats: {stats}")
    
    assert stats['handlers']['BAR'] == 1
    assert stats['handlers']['TICK'] == 1
    assert stats['middlewares'] == 1
    assert not stats['running']
    
    engine.start()
    engine.put(Event(EventType.BAR))
    engine.stop()
    
    stats = engine.get_stats()
    print(f"Stats after run: {stats}")
    assert stats['event_count'] == 3  # START + BAR + STOP
    print("✅ Stats test passed")


if __name__ == "__main__":
    print("\n" + "🧪" * 25)
    print("EventEngine 功能测试")
    print("🧪" * 25 + "\n")
    
    try:
        test_basic()
        test_error_isolation()
        test_middleware()
        test_event_propagation()
        test_stats()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
