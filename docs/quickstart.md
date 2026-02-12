# 快速开始

## 安装

### 环境要求
- Python 3.11+
- pip

### 安装步骤
```bash
# 克隆项目
git clone https://github.com/xxx/quant-plugin-framework.git
cd quant-plugin-framework

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 安装数据源依赖（可选）
pip install akshare
```

## 5 分钟运行第一个回测

### 1. 创建配置文件
```toml
# config.toml
[app]
name = "my-first-backtest"

[strategy]
name = "double_low"
params = { top_n = 5 }

[risk]
max_position_ratio = 0.3
```

### 2. 运行回测
```bash
quant run backtest --config config.toml
```

### 3. 查看结果
回测完成后会输出：
- 总收益率
- 年化收益率
- 夏普比率
- 最大回撤
- 交易记录

## 使用 Python API

```python
from contrib.strategy.double_low import DoubleLowStrategy
from contrib.backtest.simple_backtest import SimpleBacktestEngine

# 初始化策略
strategy = DoubleLowStrategy()
strategy.top_n = 5

# 初始化回测引擎
engine = SimpleBacktestEngine(
    initial_cash=100000,
    trade_mode="T+0",
)

# 准备数据（示例）
data = [...]

# 运行回测
result = engine.run(strategy, data, start_date, end_date)

# 查看结果
print(f"总收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
```

## 下一步

- [API 文档](api.md)
- [策略开发指南](strategy_guide.md)
- [插件开发指南](plugin_guide.md)
