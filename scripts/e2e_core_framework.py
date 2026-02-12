#!/usr/bin/env python3
"""核心框架端到端测试 - 验证 Week 1 各模块集成"""

import sys
sys.path.insert(0, ".")

from datetime import date
from pathlib import Path
import tempfile


def main():
    print("=" * 60)
    print("核心框架端到端测试")
    print("=" * 60)

    failed = []

    # 1. 配置管理测试
    print("\n[1] ConfigManager - 加载配置文件")
    from core.config import ConfigManager

    config_content = '''
[app]
name = "e2e-test"
debug = true

[strategy]
name = "double_low"
params = { top_n = 5, min_volume = 1000000 }

[risk]
max_position_ratio = 0.3
stop_loss_ratio = 0.05
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config = ConfigManager().load(config_path)
        print("✅ 配置加载成功")
        print(f"   app.name: {config.app.name}")
        print(f"   strategy.name: {config.strategy.name}")
        print(f"   risk.max_position_ratio: {config.risk.max_position_ratio}")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        failed.append((1, str(e)))
    finally:
        Path(config_path).unlink(missing_ok=True)

    # 2. 事件引擎测试
    print("\n[2] EventEngine - 事件注册与分发")
    from core.engine import EventEngine
    from core.events import Event, EventType

    engine = EventEngine()
    received_events = []

    def on_bar(event):
        received_events.append(event)

    try:
        engine.register_handler(EventType.BAR, on_bar)
        engine.emit(
            Event(event_type=EventType.BAR, payload={"symbol": "123001", "close": 100})
        )

        if received_events:
            print(f"✅ 事件分发成功，收到 {len(received_events)} 个事件")
            print(f"   payload: {received_events[0].payload}")
        else:
            msg = "事件分发后未收到事件"
            print(f"❌ 事件分发失败: {msg}")
            failed.append((2, msg))
    except Exception as e:
        print(f"❌ 事件引擎测试失败: {e}")
        failed.append((2, str(e)))

    # 3. Portfolio 测试
    print("\n[3] Portfolio - 仓位管理 T+1")
    from core.portfolio import Portfolio

    try:
        portfolio = Portfolio(initial_cash=100000, trade_mode="T+1")
        portfolio.buy("123001", 100, 100.0, date(2024, 1, 2))
        print("✅ 买入成功")
        print(f"   现金: {portfolio.cash:,.0f}")
        print(f"   持仓: {portfolio.get_position('123001').quantity} 股")
        print(
            f"   T+1 当日可卖: {portfolio.get_available_quantity('123001', date(2024, 1, 2))}"
        )

        portfolio.settle_day(date(2024, 1, 2))
        print(
            f"   T+1 次日可卖: {portfolio.get_available_quantity('123001', date(2024, 1, 3))}"
        )
    except Exception as e:
        print(f"❌ Portfolio 测试失败: {e}")
        failed.append((3, str(e)))
        portfolio = None

    # 4. RiskManager 测试
    print("\n[4] RiskManager - 风控规则")
    from core.risk import RiskManager, MaxPositionRatioRule, StopLossRule

    try:
        risk_manager = RiskManager()
        risk_manager.add_rule(MaxPositionRatioRule(max_ratio=0.3))
        # 当前实现参数名为 stop_loss_pct
        risk_manager.add_rule(StopLossRule(stop_loss_pct=0.05))
        print(f"✅ 风控规则配置完成，共 {len(risk_manager.rules)} 条规则")
    except Exception as e:
        print(f"❌ RiskManager 测试失败: {e}")
        failed.append((4, str(e)))
        risk_manager = None

    # 5. Cache 测试
    print("\n[5] CacheManager - 缓存读写")
    from core.cache import CacheManager, MemoryCache

    try:
        cache = CacheManager(MemoryCache())
        cache.backend.set("test_key", {"data": [1, 2, 3]}, ttl=60)
        cached = cache.backend.get("test_key")

        if cached:
            print("✅ 缓存读写成功")
            print(f"   cached data: {cached}")
        else:
            msg = "写入后读取为空"
            print(f"❌ 缓存读写失败: {msg}")
            failed.append((5, msg))
    except Exception as e:
        print(f"❌ Cache 测试失败: {e}")
        failed.append((5, str(e)))

    # 6. Context 测试
    print("\n[6] Context - 上下文管理")
    from core.context import Context, get_current_context
    from core.config import FrameworkConfig
    from core.logger import get_logger

    try:
        if portfolio is None or risk_manager is None:
            raise RuntimeError("依赖对象未初始化（portfolio/risk_manager）")

        ctx = Context(
            config=FrameworkConfig(),
            portfolio=portfolio,
            risk_manager=risk_manager,
            event_engine=engine,
            logger=get_logger("e2e_context"),
        )

        with ctx:
            current = get_current_context()
            if current is ctx:
                print("✅ 上下文管理成功")
                print(f"   portfolio.cash: {current.portfolio.cash:,.0f}")
            else:
                msg = "with 内获取的 current 不是当前 ctx"
                print(f"❌ 上下文获取失败: {msg}")
                failed.append((6, msg))
    except Exception as e:
        print(f"❌ Context 测试失败: {e}")
        failed.append((6, str(e)))

    # 7. Logger 测试
    print("\n[7] Logger - 日志输出")
    from core.logger import setup_logging, get_logger

    try:
        setup_logging({"level": "INFO"})
        logger = get_logger("e2e_test")
        logger.info("端到端测试日志输出")
        print("✅ 日志配置成功")
    except Exception as e:
        print(f"❌ Logger 测试失败: {e}")
        failed.append((7, str(e)))

    # 8. Exceptions 测试
    print("\n[8] Exceptions - 异常处理")
    from core.exceptions import QuantError, DataError, wrap_exception

    try:
        _ = wrap_exception(ValueError("bad"), DataError, "包装异常")
        try:
            raise DataError("测试数据异常", code="DATA_001", context={"symbol": "123001"})
        except QuantError as e:
            print("✅ 异常捕获成功")
            print(f"   message: {e.message}")
            print(f"   code: {e.code}")
    except Exception as e:
        print(f"❌ Exceptions 测试失败: {e}")
        failed.append((8, str(e)))

    # 9. PluginManager 测试
    print("\n[9] PluginManager - 插件管理")
    from plugins.manager import PluginManager
    from plugins.base import Plugin

    class TestPlugin(Plugin):
        name = "test_plugin"
        version = "1.0.0"

    try:
        manager = PluginManager()
        manager.register(TestPlugin())
        print(f"✅ 插件注册成功，共 {len(manager.get_all())} 个插件")
    except Exception as e:
        print(f"❌ PluginManager 测试失败: {e}")
        failed.append((9, str(e)))

    print("\n" + "=" * 60)
    if failed:
        print("核心框架端到端测试完成（存在失败）")
        for idx, err in failed:
            print(f" - 模块[{idx}] 失败: {err}")
    else:
        print("核心框架端到端测试完成（9/9 全部通过）")
    print("=" * 60)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
