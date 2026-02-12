"""AKShare data source plugin tests (Day 8, TDD).

All tests use mocks and do not call real AKShare APIs.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = PROJECT_ROOT / "contrib" / "data" / "akshare_source.py"


def _load_plugin_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("day8_akshare_source", PLUGIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load akshare_source module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["day8_akshare_source"] = module
    spec.loader.exec_module(module)
    return module


def _build_fake_frame(records: list[dict[str, Any]]) -> Any:
    frame = SimpleNamespace()
    frame.to_dict = lambda orient="records": records  # noqa: ARG005
    return frame


def test_fetch_cb_list_returns_records() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        bond_zh_cov=Mock(
            return_value=_build_fake_frame(
                [
                    {"代码": "110001", "名称": "南山转债"},
                    {"代码": "113001", "名称": "平安转债"},
                ]
            )
        )
    )
    module.ak = mock_ak

    rows = source.fetch_cb_list()

    assert len(rows) == 2
    assert rows[0]["代码"] == "110001"
    mock_ak.bond_zh_cov.assert_called_once_with()


def test_fetch_cb_realtime_filters_codes() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        bond_zh_hs_cov_spot=Mock(
            return_value=_build_fake_frame(
                [
                    {"代码": "110001", "最新价": 101.2},
                    {"代码": "113001", "最新价": 99.8},
                ]
            )
        )
    )
    module.ak = mock_ak

    rows = source.fetch_cb_realtime(["110001"])

    assert rows == [{"代码": "110001", "最新价": 101.2}]
    mock_ak.bond_zh_hs_cov_spot.assert_called_once_with()


def test_fetch_cb_history_returns_normalized_bars() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        bond_zh_hs_cov_daily=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "日期": "2026-01-02",
                        "开盘": 100,
                        "最高": 102,
                        "最低": 99,
                        "收盘": 101,
                        "成交量": 10000,
                        "成交额": 1234567,
                    }
                ]
            )
        )
    )
    module.ak = mock_ak

    bars = source.fetch_cb_history("110001", date(2026, 1, 1), date(2026, 1, 10))

    assert len(bars) == 1
    assert bars[0]["symbol"] == "110001"
    assert isinstance(bars[0]["datetime"], datetime)
    assert bars[0]["close"] == 101.0


def test_fetch_cb_history_filters_by_date_range() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        bond_zh_hs_cov_daily=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "日期": "2026-01-01",
                        "开盘": 100,
                        "最高": 102,
                        "最低": 99,
                        "收盘": 101,
                        "成交量": 10000,
                        "成交额": 1234567,
                    },
                    {
                        "日期": "2026-01-05",
                        "开盘": 101,
                        "最高": 103,
                        "最低": 100,
                        "收盘": 102,
                        "成交量": 11000,
                        "成交额": 1334567,
                    },
                    {
                        "日期": "2026-01-10",
                        "开盘": 102,
                        "最高": 104,
                        "最低": 101,
                        "收盘": 103,
                        "成交量": 12000,
                        "成交额": 1434567,
                    },
                ]
            )
        )
    )
    module.ak = mock_ak

    bars = source.fetch_cb_history("110001", date(2026, 1, 2), date(2026, 1, 8))

    assert len(bars) == 1
    assert bars[0]["datetime"].date() == date(2026, 1, 5)


def test_fetch_stock_daily_returns_normalized_bars() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        stock_zh_a_hist=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "日期": "2026-01-03",
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9.5,
                        "收盘": 10.5,
                        "成交量": 200000,
                        "成交额": 3000000,
                    }
                ]
            )
        )
    )
    module.ak = mock_ak

    bars = source.fetch_stock_daily("600000", date(2026, 1, 1), date(2026, 1, 31))

    assert len(bars) == 1
    assert bars[0]["symbol"] == "600000"
    assert bars[0]["open"] == 10.0
    mock_ak.stock_zh_a_hist.assert_called_once_with(
        symbol="600000", start_date="20260101", end_date="20260131", adjust=""
    )


def test_normalize_bar_standard_format() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    bar = source._normalize_bar(
        {
            "日期": "2026-02-10",
            "开盘": "1.1",
            "最高": "1.3",
            "最低": "1.0",
            "收盘": "1.2",
            "成交量": "1000",
            "成交额": "2000",
        },
        symbol="110001",
    )

    assert set(bar.keys()) == {
        "symbol",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    }
    assert bar["symbol"] == "110001"
    assert isinstance(bar["datetime"], datetime)
    assert bar["volume"] == 1000


def test_cache_hit_skips_api_call() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    mock_ak = SimpleNamespace(
        bond_zh_cov=Mock(return_value=_build_fake_frame([{"代码": "110001"}]))
    )
    module.ak = mock_ak

    first = source.fetch_cb_list()
    second = source.fetch_cb_list()

    assert first == second
    mock_ak.bond_zh_cov.assert_called_once_with()


def test_api_error_raises_runtime_error() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    module.ak = SimpleNamespace(bond_zh_cov=Mock(side_effect=ValueError("boom")))

    with pytest.raises(RuntimeError, match="fetch_cb_list"):
        source.fetch_cb_list()


def test_realtime_fetch_latency_less_than_3_seconds() -> None:
    module = _load_plugin_module()
    source = module.AKShareDataSource()

    def _fast_spot() -> Any:
        time.sleep(0.02)
        return _build_fake_frame([{"代码": "110001", "最新价": 101.0}])

    module.ak = SimpleNamespace(bond_zh_hs_cov_spot=Mock(side_effect=_fast_spot))

    start = time.perf_counter()
    rows = source.fetch_cb_realtime(["110001"])
    elapsed = time.perf_counter() - start

    assert rows[0]["代码"] == "110001"
    assert elapsed < 3.0
