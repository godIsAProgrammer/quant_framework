# quant-plugin-framework

插件化量化交易框架（Day 1/Day 2 核心模块）。

## 当前实现

- `core/events.py`：
  - `Event` 基础事件模型
  - `EventType` 枚举及 12 种事件类型（TICK/BAR/ORDER/TRADE/POSITION/SIGNAL/RISK/LOG/ERROR/START/STOP/HEARTBEAT）
- `core/engine.py`：
  - 事件处理器注册与注销
  - 事件同步/异步分发（`emit`/`dispatch`/`emit_async`/`dispatch_async`）
  - 中间件链支持（支持同步或异步中间件）
  - 错误隔离（中间件/处理器异常互不影响）
  - 错误事件上报（`ERROR` 事件，含 stage/target/error_type/error_message）
  - 防递归保护（避免 `ERROR` 事件上报无限递归）
- `core/config.py`：
  - `ConfigManager` 配置加载器
  - TOML 配置解析
  - Pydantic 模型验证
  - 默认配置 + 深度合并覆盖
  - 示例配置：`config/example.toml`
- 测试覆盖：
  - `tests/core/test_engine.py`
  - `tests/core/test_config.py`

## 开发与测试

```bash
cd ~/Projects/quant-plugin-framework
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## 质量约束

- PEP8 / black
- 完整类型注解（mypy strict）
- 公共方法 docstring
