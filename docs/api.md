# API 参考

## 核心模块

### EventEngine

事件引擎，负责事件注册与分发，支持同步/异步处理、中间件链和错误隔离。

```python
from core.engine import EventEngine
from core.events import Event, EventType


def on_bar(event: Event) -> None:
    print("收到 BAR 事件:", event.payload)


engine = EventEngine()

# 注册处理器
engine.register_handler(EventType.BAR, on_bar)

# 发送事件
engine.emit(Event(event_type=EventType.BAR, payload={"symbol": "110001"}))
```

常用方法：
- `register_handler(event_type, handler)`: 注册事件处理器
- `unregister_handler(event_type, handler)`: 注销处理器
- `add_middleware(middleware)`: 添加中间件
- `emit(event)`: 同步发送事件
- `emit_async(event)`: 异步发送事件

---

### ConfigManager

配置管理，加载 TOML 配置文件并做校验（基于 Pydantic）。

```python
from core.config import ConfigManager

cfg = ConfigManager().load("config.toml")
print(cfg.strategy.name)
print(cfg.strategy.params.top_n)
```

常用方法：
- `load(path)`: 从 TOML 文件加载配置
- `from_dict(data)`: 从字典加载并校验

---

### Portfolio

仓位管理，支持 `T+0` / `T+1` 交易模式，内置买卖撮合后的仓位与资金更新。

```python
from datetime import date
from core.portfolio import Portfolio

portfolio = Portfolio(initial_cash=100000, trade_mode="T+1")
portfolio.buy("110001", quantity=100, price=100.0, date=date(2026, 1, 1))
portfolio.settle_day(date(2026, 1, 1))  # T+1 解锁可卖数量
portfolio.sell("110001", quantity=50, price=101.0, date=date(2026, 1, 2))
```

常用方法：
- `buy(symbol, quantity, price, date)`: 买入
- `sell(symbol, quantity, price, date)`: 卖出
- `get_position(symbol)`: 查询持仓
- `get_total_value(prices)`: 计算总资产
- `settle_day(date)`: 日终结算（T+1）

---

### RiskManager

风控管理，支持多种风控规则组合校验。

内置规则包括：
- `StopLossRule`: 止损
- `TakeProfitRule`: 止盈
- `MaxPositionRatioRule`: 单标的仓位占比限制
- `MaxHoldingsRule`: 持仓标的数量限制
- `MaxTradeAmountRule`: 单笔交易金额限制

```python
from core.risk import RiskManager, MaxPositionRatioRule
from core.portfolio import Portfolio

risk_manager = RiskManager([MaxPositionRatioRule(0.3)])
portfolio = Portfolio(initial_cash=100000)

order = {"side": "BUY", "symbol": "110001", "quantity": 100, "price": 100.0}
result = risk_manager.check_order(order, portfolio, prices={"110001": 100.0})
print(result.passed, result.violations)
```

---

### Context

运行时上下文，传递组件引用（配置、仓位、风控、事件引擎、日志）与自定义共享数据。

```python
import logging
from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager

ctx = Context(
    config=FrameworkConfig(),
    portfolio=Portfolio(initial_cash=100000),
    risk_manager=RiskManager(),
    event_engine=EventEngine(),
    logger=logging.getLogger("demo"),
)

ctx.set("run_id", "bt-001")
print(ctx.get("run_id"))
```

## 策略模块

### DoubleLowStrategy

双低可转债策略（`contrib.strategy.double_low.DoubleLowStrategy`）。

**参数**:
- `top_n`: 持仓数量，默认 10
- `min_volume`: 最小成交量，默认 1,000,000
- `rebalance_days`: 调仓周期，默认 5

**方法**:
- `on_init(context)`: 初始化
- `on_bar(context, bar)`: 处理 K 线数据并返回交易信号

```python
from contrib.strategy.double_low import DoubleLowStrategy

strategy = DoubleLowStrategy()
strategy.top_n = 10
strategy.min_volume = 1_000_000
strategy.rebalance_days = 5
```

## 回测模块

### SimpleBacktestEngine

简单回测引擎（`contrib.backtest.simple_backtest.SimpleBacktestEngine`）。

**参数**:
- `initial_cash`: 初始资金
- `trade_mode`: `"T+0"` 或 `"T+1"`
- `commission_rate`: 手续费率
- `slippage`: 滑点

**方法**:
- `run(strategy, data, start_date, end_date)`: 运行回测

```python
from datetime import date
from contrib.backtest.simple_backtest import SimpleBacktestEngine
from contrib.strategy.double_low import DoubleLowStrategy

engine = SimpleBacktestEngine(
    initial_cash=100_000,
    trade_mode="T+0",
    commission_rate=0.0003,
    slippage=0.001,
)

strategy = DoubleLowStrategy()
result = engine.run(
    strategy=strategy,
    data=[],
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 31),
)
print(result.total_return)
```

### BacktestResult

回测结果数据类。

**属性**:
- `total_return`: 总收益率
- `annual_return`: 年化收益率
- `sharpe_ratio`: 夏普比率
- `max_drawdown`: 最大回撤
- `win_rate`: 胜率
- `trade_count`: 交易次数

（另包含 `initial_cash`、`final_value`、`net_value_series`、`trades` 等字段）

## 插件模块

### Plugin

插件基类（`plugins.base.Plugin`），定义统一生命周期：
- `setup(context)`: 初始化
- `teardown(context)`: 销毁
- `enable()`: 启用插件
- `disable()`: 禁用插件

### PluginManager

插件管理器（`plugins.manager.PluginManager`），负责：
- 插件注册/反注册
- 依赖校验与拓扑排序初始化
- 生命周期管理（`initialize` / `shutdown`）
- Hook 广播调用（`call_hook`）
