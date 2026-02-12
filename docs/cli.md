# 命令行工具

## 安装

确保已安装项目：

```bash
pip install -e .
```

> 说明：当前仓库 `pyproject.toml` 尚未声明 `console_scripts` 入口。若本机未生成 `quant` 命令，可临时用以下方式调用：
>
> ```bash
> python -m cli.main --help
> ```

## 命令

### quant run backtest

运行回测。

```bash
quant run backtest --config config.toml
```

**参数**:
- `--config, -c`: 配置文件路径
- `--strategy, -s`: 策略名称（默认：`double_low`）
- `--start`: 开始日期（Click DateTime 格式）
- `--end`: 结束日期（Click DateTime 格式）

示例：

```bash
quant run backtest \
  --config config.toml \
  --strategy double_low \
  --start "2026-01-01" \
  --end "2026-01-31"
```

### quant --version

显示版本。

```bash
quant --version
```

### quant --help

显示帮助。

```bash
quant --help
```
