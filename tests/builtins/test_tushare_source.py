"""Tushare data source plugin tests (Day 15, TDD)."""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from plugins.protocols import DataSourceProtocol

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = PROJECT_ROOT / "builtins" / "data" / "tushare_source.py"


@pytest.fixture(autouse=True)
def _clean_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)


def _load_plugin_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("day15_tushare_source", PLUGIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tushare_source module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["day15_tushare_source"] = module
    spec.loader.exec_module(module)
    return module


def _build_fake_frame(records: list[dict[str, Any]]) -> Any:
    frame = SimpleNamespace()
    frame.empty = len(records) == 0
    frame.to_dict = lambda orient="records": records  # noqa: ARG005
    return frame


def test_init_requires_tushare_token(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_plugin_module()

    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TUSHARE_TOKEN"):
        module.TushareDataSource()


def test_fetch_stock_list_returns_akshare_like_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(
        stock_basic=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "symbol": "000001",
                        "name": "平安银行",
                    },
                    {
                        "ts_code": "600000.SH",
                        "symbol": "600000",
                        "name": "浦发银行",
                    },
                ]
            )
        )
    )
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()
    rows = source.fetch_stock_list()

    assert rows[0]["代码"] == "000001"
    assert rows[0]["名称"] == "平安银行"
    assert rows[1]["ts_code"] == "600000.SH"
    pro.stock_basic.assert_called_once()


def test_fetch_stock_history_returns_normalized_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(
        daily=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260103",
                        "open": 10,
                        "high": 11,
                        "low": 9.8,
                        "close": 10.5,
                        "vol": 200000,
                        "amount": 3000000,
                    },
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260102",
                        "open": 9.9,
                        "high": 10.2,
                        "low": 9.7,
                        "close": 10.0,
                        "vol": 180000,
                        "amount": 2600000,
                    },
                ]
            )
        )
    )
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()
    bars = source.fetch_stock_history("000001", date(2026, 1, 1), date(2026, 1, 10))

    assert len(bars) == 2
    assert bars[0]["datetime"] == datetime(2026, 1, 2)
    assert bars[1]["datetime"] == datetime(2026, 1, 3)
    assert bars[0]["symbol"] == "000001"


def test_fetch_cb_list_returns_records(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(
        cb_basic=Mock(
            return_value=_build_fake_frame(
                [
                    {
                        "ts_code": "110001.SH",
                        "bond_short_name": "南山转债",
                    }
                ]
            )
        )
    )
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()
    rows = source.fetch_cb_list()

    assert rows == [{"代码": "110001", "名称": "南山转债", "ts_code": "110001.SH"}]


def test_fetch_cb_history_raises_when_data_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(cb_daily=Mock(return_value=_build_fake_frame([])))
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()

    with pytest.raises(RuntimeError, match="no data"):
        source.fetch_cb_history("110001", date(2026, 1, 1), date(2026, 1, 10))


def test_rate_limit_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(stock_basic=Mock(side_effect=Exception("429 too many requests")))
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()

    with pytest.raises(RuntimeError, match="rate limit"):
        source.fetch_stock_list()


def test_cache_hit_skips_second_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    pro = SimpleNamespace(
        stock_basic=Mock(
            return_value=_build_fake_frame(
                [{"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行"}]
            )
        )
    )
    module.ts = SimpleNamespace(set_token=Mock(), pro_api=Mock(return_value=pro))

    source = module.TushareDataSource()

    first = source.fetch_stock_list()
    second = source.fetch_stock_list()

    assert first == second
    pro.stock_basic.assert_called_once()


def test_implements_datasource_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_plugin_module()
    monkeypatch.setenv("TUSHARE_TOKEN", "token")

    module.ts = SimpleNamespace(
        set_token=Mock(),
        pro_api=Mock(return_value=SimpleNamespace()),
    )

    source = module.TushareDataSource()
    assert isinstance(source, DataSourceProtocol)
