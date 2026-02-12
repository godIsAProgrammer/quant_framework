"""P0 integration tests: backtest flow, risk, T+1, config, plugin lifecycle, event engine."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from contrib.backtest.simple_backtest import SimpleBacktestEngine
from contrib.risk.basic_risk_plugin import BasicRiskPlugin
from contrib.strategy.double_low import DoubleLowStrategy
from core.config import ConfigManager, FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.events import BAR, ORDER, TRADE, Event
from core.portfolio import Portfolio
from core.risk import RiskManager
from plugins.base import Plugin
from plugins.manager import PluginManager


class MockCBDataSource:
    """Mock convertible-bond data source for integration tests."""

    def fetch_cb_realtime(self) -> list[dict[str, Any]]:
        return [
            {"symbol": "CB001", "price": 95.0, "premium_rate": 0.10},
            {"symbol": "CB002", "price": 97.0, "premium_rate": 0.12},
            {"symbol": "CB003", "price": 100.0, "premium_rate": 0.30},
        ]

    def fetch_cb_history(self, start: date, end: date) -> list[dict[str, Any]]:
        _ = (start, end)
        return [
            {
                "date": date(2026, 1, 2),
                "symbol": "CB001",
                "close": 95.0,
                "price": 95.0,
                "premium_rate": 0.10,
                "volume": 3_000_000,
                "days_to_maturity": 200,
            },
            {
                "date": date(2026, 1, 2),
                "symbol": "CB002",
                "close": 97.0,
                "price": 97.0,
                "premium_rate": 0.12,
                "volume": 3_000_000,
                "days_to_maturity": 210,
            },
            {
                "date": date(2026, 1, 3),
                "symbol": "CB001",
                "close": 102.0,
                "price": 102.0,
                "premium_rate": 0.40,
                "volume": 3_000_000,
                "days_to_maturity": 199,
            },
            {
                "date": date(2026, 1, 3),
                "symbol": "CB002",
                "close": 96.0,
                "price": 96.0,
                "premium_rate": 0.08,
                "volume": 3_000_000,
                "days_to_maturity": 209,
            },
            {
                "date": date(2026, 1, 4),
                "symbol": "CB001",
                "close": 101.0,
                "price": 101.0,
                "premium_rate": 0.38,
                "volume": 3_000_000,
                "days_to_maturity": 198,
            },
            {
                "date": date(2026, 1, 4),
                "symbol": "CB002",
                "close": 98.0,
                "price": 98.0,
                "premium_rate": 0.11,
                "volume": 3_000_000,
                "days_to_maturity": 208,
            },
        ]


def _build_context(initial_cash: float = 100_000.0, trade_mode: str = "T+0") -> Context:
    return Context(
        config=FrameworkConfig(),
        portfolio=Portfolio(initial_cash=initial_cash, trade_mode=trade_mode),
        risk_manager=RiskManager(),
        event_engine=EventEngine(),
        logger=logging.getLogger("test.integration.p0"),
    )


def test_double_low_backtest_flow() -> None:
    """双低策略完整回测流程。"""
    # 1) 加载配置
    cfg = FrameworkConfig()

    # 2) 初始化数据源
    source = MockCBDataSource()

    # 3) 获取可转债数据
    realtime = source.fetch_cb_realtime()
    history = source.fetch_cb_history(start=date(2026, 1, 2), end=date(2026, 1, 4))

    # 4) 初始化双低策略
    strategy = DoubleLowStrategy()
    strategy.top_n = 1
    strategy.min_volume = 1
    strategy.rebalance_days = 1

    # 5) 初始化回测引擎
    engine = SimpleBacktestEngine(
        initial_cash=100_000,
        trade_mode="T+0",
        commission_rate=0.0,
        slippage=0.0,
    )

    # 6) 运行回测
    result = engine.run(
        strategy=strategy,
        data=history,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    # 7) 验证结果
    assert cfg.app.name == "quant-framework"
    assert len(realtime) > 0
    assert result.trade_count > 0
    assert result.final_value > 0
    assert -1.0 < result.total_return < 10.0
    assert 0.0 <= result.max_drawdown <= 1.0


def test_risk_control_blocks_large_order() -> None:
    """风控拦截超限订单。"""
    context = _build_context(initial_cash=100_000)
    plugin = BasicRiskPlugin(max_position_ratio=0.3, max_trade_ratio=1.0)

    order = {
        "symbol": "CB001",
        "side": "BUY",
        "quantity": 400,  # 40,000 / 100,000 = 40% > 30%
        "price": 100.0,
        "order_type": "MARKET",
    }

    blocked = plugin.on_order(context, order)
    check = plugin.check_order(order, context)

    assert blocked is None
    assert check.passed is False
    assert any("position" in v.lower() for v in check.violations)


def test_t1_mode_blocks_same_day_sell() -> None:
    """T+1 模式下当日买入不可卖，次日可卖。"""

    class T1Strategy:
        def on_init(self, context: Context) -> None:
            context.set("step", 0)

        def on_bar(self, context: Context, bar: dict[str, Any]) -> list[dict[str, Any]]:
            step = int(context.get("step", 0))
            context.set("step", step + 1)
            symbol = str(bar["cb_data"][0]["symbol"])
            if step == 0:
                return [
                    {
                        "symbol": symbol,
                        "side": "BUY",
                        "quantity": 10,
                        "order_type": "MARKET",
                    },
                    {
                        "symbol": symbol,
                        "side": "SELL",
                        "quantity": 10,
                        "order_type": "MARKET",
                    },
                ]
            if step == 1:
                return [
                    {
                        "symbol": symbol,
                        "side": "SELL",
                        "quantity": 10,
                        "order_type": "MARKET",
                    },
                ]
            return []

    bars = [
        {"date": date(2026, 1, 2), "symbol": "CB001", "close": 100.0},
        {"date": date(2026, 1, 3), "symbol": "CB001", "close": 101.0},
    ]

    engine = SimpleBacktestEngine(
        initial_cash=100_000,
        trade_mode="T+1",
        commission_rate=0.0,
        slippage=0.0,
    )
    result = engine.run(
        strategy=T1Strategy(),
        data=bars,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 3),
    )

    sells = [t for t in result.trades if t["side"] == "SELL"]
    assert result.trade_count == 2  # day1 buy + day2 sell
    assert len(sells) == 1
    assert sells[0]["date"] == date(2026, 1, 3)


def test_config_driven_backtest(tmp_path: Path) -> None:
    """从配置文件驱动回测。"""
    config_path = tmp_path / "p0_config.toml"
    config_path.write_text(
        """
[app]
name = "p0-integration"
debug = true

[strategy]
name = "double_low"

[strategy.params]
top_n = 1
min_volume = 1

[backtest]
initial_cash = 120000
trade_mode = "T+0"
commission_rate = 0.0
slippage = 0.0
""".strip(),
        encoding="utf-8",
    )

    cfg = ConfigManager().load(config_path)
    backtest_cfg = getattr(cfg, "backtest")

    strategy = DoubleLowStrategy()
    strategy.top_n = int(cfg.strategy.params.top_n)
    strategy.min_volume = int(cfg.strategy.params.min_volume)
    strategy.rebalance_days = 1

    engine = SimpleBacktestEngine(
        initial_cash=float(backtest_cfg["initial_cash"]),
        trade_mode=str(backtest_cfg["trade_mode"]),
        commission_rate=float(backtest_cfg["commission_rate"]),
        slippage=float(backtest_cfg["slippage"]),
    )

    data = MockCBDataSource().fetch_cb_history(date(2026, 1, 2), date(2026, 1, 4))
    result = engine.run(
        strategy=strategy,
        data=data,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    assert cfg.app.name == "p0-integration"
    assert result.initial_cash == 120_000
    assert result.trade_count > 0


def test_plugin_manager_lifecycle() -> None:
    """插件生命周期管理：依赖顺序初始化、逆序关闭、钩子调用。"""
    events: list[str] = []

    class TrackedPlugin(Plugin):
        def __init__(self, name: str, dependencies: list[str] | None = None) -> None:
            super().__init__()
            self.name = name
            self.dependencies = dependencies or []

        def setup(self, context: Context) -> None:
            _ = context
            events.append(f"setup:{self.name}")

        def teardown(self, context: Context) -> None:
            _ = context
            events.append(f"teardown:{self.name}")

        def on_bar(self, payload: str) -> str:
            events.append(f"hook:{self.name}:{payload}")
            return f"{self.name}:{payload}"

    manager = PluginManager()
    manager.register(TrackedPlugin("data"))
    manager.register(TrackedPlugin("risk", dependencies=["data"]))
    manager.register(TrackedPlugin("strategy", dependencies=["risk"]))

    ctx = _build_context()
    manager.initialize(ctx)
    results = manager.call_hook("on_bar", "BAR")
    manager.shutdown(ctx)

    assert events[:3] == ["setup:data", "setup:risk", "setup:strategy"]
    assert results == ["data:BAR", "risk:BAR", "strategy:BAR"]
    assert events[-3:] == ["teardown:strategy", "teardown:risk", "teardown:data"]


def test_event_driven_trading() -> None:
    """事件驱动交易流程：BAR -> ORDER -> TRADE。"""
    engine = EventEngine()

    seen: list[str] = []
    orders: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []

    def on_bar(event: Event) -> None:
        seen.append("BAR")
        bar = event.payload
        order = {
            "symbol": bar["symbol"],
            "side": "BUY",
            "quantity": 10,
            "price": float(bar["close"]),
        }
        engine.emit(Event(event_type=ORDER, payload=order, source="strategy"))

    def on_order(event: Event) -> None:
        seen.append("ORDER")
        order = event.payload
        orders.append(order)
        trade = {
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": order["quantity"],
            "price": order["price"],
            "amount": order["quantity"] * order["price"],
        }
        engine.emit(Event(event_type=TRADE, payload=trade, source="matcher"))

    def on_trade(event: Event) -> None:
        seen.append("TRADE")
        trades.append(event.payload)

    engine.register_handler(BAR, on_bar)
    engine.register_handler(ORDER, on_order)
    engine.register_handler(TRADE, on_trade)

    engine.emit(
        Event(
            event_type=BAR,
            payload={"symbol": "CB001", "close": 100.0},
            source="market",
        )
    )

    assert seen == ["BAR", "ORDER", "TRADE"]
    assert len(orders) == 1
    assert len(trades) == 1
    assert trades[0]["amount"] == 1000.0
