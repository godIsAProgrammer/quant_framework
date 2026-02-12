"""
AKShare 数据源集成测试 - 调用真实 API
运行方式: pytest tests/integration/ -m integration -v
"""

from __future__ import annotations

import importlib.util
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# 标记为集成测试
pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = PROJECT_ROOT / "contrib" / "data" / "akshare_source.py"


def _load_plugin_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "integration_akshare_source", PLUGIN_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load akshare_source module spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules["integration_akshare_source"] = module
    spec.loader.exec_module(module)
    return module


def _first_value(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


@pytest.fixture
def source():
    module = _load_plugin_module()
    if getattr(module, "ak", None) is None:
        pytest.skip("akshare is not installed")
    return module.AKShareDataSource()


@pytest.fixture(autouse=True)
def _throttle_requests():
    """简单限速，降低触发 AKShare 接口频控的概率。"""
    yield
    time.sleep(0.8)


class TestAKShareIntegration:
    """真实 API 集成测试"""

    def test_fetch_cb_list_real(self, source) -> None:
        """测试获取真实可转债列表"""
        rows = source.fetch_cb_list()

        assert isinstance(rows, list)
        assert len(rows) > 0

        first = rows[0]
        assert isinstance(first, dict)

        # AKShare 字段可能随版本变化：兼容常见代码/名称列
        code = _first_value(first, ["代码", "债券代码", "转债代码", "证券代码"])
        name = _first_value(first, ["名称", "债券简称", "转债名称", "证券简称"])

        assert code is not None
        assert str(code).strip() != ""
        assert name is not None
        assert str(name).strip() != ""

    def test_fetch_cb_realtime_real(self, source) -> None:
        """测试获取真实可转债实时行情"""
        try:
            all_rows = source.fetch_cb_realtime([])
        except RuntimeError as exc:
            pytest.skip(f"AKShare realtime API unavailable: {exc}")

        assert isinstance(all_rows, list)
        assert len(all_rows) > 0

        first = all_rows[0]
        assert isinstance(first, dict)
        assert len(first) > 0

        # 行情字段在不同数据源版本下可能不同，至少应有一个数值字段
        has_numeric_value = any(isinstance(v, (int, float)) for v in first.values())
        assert has_numeric_value

        # 插件当前按“代码”字段过滤；若实时接口无该字段则跳过过滤断言
        code = _first_value(first, ["代码"])
        if code is None:
            pytest.skip("Realtime payload has no '代码' field; skip filter assertion")

        rows = source.fetch_cb_realtime([str(code)])
        assert isinstance(rows, list)
        assert len(rows) >= 1

        returned_codes = {str(row.get("代码", "")).strip() for row in rows}
        assert str(code).strip() in returned_codes

    def test_fetch_stock_daily_real(self, source) -> None:
        """测试获取真实股票日线"""
        end = date.today()
        start = end - timedelta(days=30)

        try:
            # 贵州茅台
            bars = source.fetch_stock_daily("600519", start, end)
        except RuntimeError as exc:
            pytest.skip(f"AKShare stock daily API unavailable: {exc}")

        assert isinstance(bars, list)
        assert len(bars) > 0

        first = bars[0]
        required_fields = {
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        }
        assert required_fields.issubset(first.keys())
        assert first["symbol"] == "600519"

    def test_api_response_time(self, source) -> None:
        """测试 API 响应时间 < 5 秒"""
        start = time.perf_counter()
        try:
            rows = source.fetch_cb_realtime([])
        except RuntimeError as exc:
            pytest.skip(f"AKShare realtime API unavailable: {exc}")
        elapsed = time.perf_counter() - start

        assert isinstance(rows, list)
        assert len(rows) > 0
        assert elapsed < 5.0, f"AKShare realtime API took too long: {elapsed:.3f}s"
