"""Tushare data source plugin.

Provides stock/convertible-bond list and history APIs with normalization,
caching, and robust exception handling.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, cast

from core.cache import CacheManager, MemoryCache
from plugins.base import Plugin

try:
    import tushare as ts
except ImportError:  # pragma: no cover - tests patch module-level ts directly
    ts = None


class TushareDataSource(Plugin):
    """Tushare 数据源插件，作为 AKShare 备用源。"""

    name = "tushare"
    version = "1.0.0"
    description = "Tushare data source for A-share and convertible bond"

    def __init__(self) -> None:
        super().__init__()
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TUSHARE_TOKEN is required for TushareDataSource")

        if ts is None:
            raise RuntimeError("tushare is not installed")

        ts.set_token(token)
        self._pro = ts.pro_api()
        self._cache = CacheManager(MemoryCache())

    # ----- protocol compatibility -----
    def fetch_bars(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        """Compatibility method for DataSourceProtocol."""
        return self.fetch_stock_history(symbol, start, end)

    def fetch_realtime(self, symbol: str) -> dict[str, Any]:
        """Realtime is not implemented in current Tushare fallback."""
        _ = symbol
        raise NotImplementedError("Tushare realtime fetch is not implemented")

    # ----- day15 required APIs -----
    def fetch_stock_list(self) -> list[dict[str, Any]]:
        """获取股票列表。"""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._pro.stock_basic(
                    exchange="", list_status="L", fields="ts_code,symbol,name"
                )
                rows = self._to_records(frame)
                return [
                    {
                        "代码": str(row.get("symbol", "")),
                        "名称": str(row.get("name", "")),
                        "ts_code": str(row.get("ts_code", "")),
                    }
                    for row in rows
                ]
            except Exception as exc:  # noqa: BLE001
                raise self._map_exception("fetch_stock_list", exc) from exc

        key = self._cache.cache_key("ts_stock_list")
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=300.0)
        )

    def fetch_stock_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """获取股票历史数据，格式与 AKShare 标准化输出一致。"""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._pro.daily(
                    ts_code=self._to_tushare_code(symbol),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                )
                rows = self._to_records(frame)
                if not rows:
                    raise RuntimeError("no data")
                bars = [self._normalize_bar(row, symbol) for row in rows]
                return sorted(bars, key=lambda x: cast(datetime, x["datetime"]))
            except Exception as exc:  # noqa: BLE001
                raise self._map_exception("fetch_stock_history", exc) from exc

        key = self._cache.cache_key("ts_stock_history", symbol, start, end)
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=300.0)
        )

    def fetch_cb_list(self) -> list[dict[str, Any]]:
        """获取可转债列表。"""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._pro.cb_basic(fields="ts_code,bond_short_name")
                rows = self._to_records(frame)
                return [
                    {
                        "代码": str(row.get("ts_code", "")).split(".")[0],
                        "名称": str(row.get("bond_short_name", "")),
                        "ts_code": str(row.get("ts_code", "")),
                    }
                    for row in rows
                ]
            except Exception as exc:  # noqa: BLE001
                raise self._map_exception("fetch_cb_list", exc) from exc

        key = self._cache.cache_key("ts_cb_list")
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=300.0)
        )

    def fetch_cb_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """获取可转债历史数据，格式与 AKShare 标准化输出一致。"""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._pro.cb_daily(
                    ts_code=self._to_tushare_code(symbol),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                )
                rows = self._to_records(frame)
                if not rows:
                    raise RuntimeError("no data")
                bars = [self._normalize_bar(row, symbol) for row in rows]
                return sorted(bars, key=lambda x: cast(datetime, x["datetime"]))
            except Exception as exc:  # noqa: BLE001
                raise self._map_exception("fetch_cb_history", exc) from exc

        key = self._cache.cache_key("ts_cb_history", symbol, start, end)
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=300.0)
        )

    # ----- internals -----
    @staticmethod
    def _to_records(frame: Any) -> list[dict[str, Any]]:
        if hasattr(frame, "to_dict"):
            records = frame.to_dict(orient="records")
            if isinstance(records, list):
                return [dict(item) for item in records]
        return []

    @staticmethod
    def _to_tushare_code(symbol: str) -> str:
        if "." in symbol:
            return symbol
        if symbol.startswith(("6", "9")):
            return f"{symbol}.SH"
        return f"{symbol}.SZ"

    @staticmethod
    def _normalize_bar(raw: dict[str, Any], symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "datetime": TushareDataSource._parse_datetime(raw.get("trade_date")),
            "open": float(raw.get("open", 0.0)),
            "high": float(raw.get("high", 0.0)),
            "low": float(raw.get("low", 0.0)),
            "close": float(raw.get("close", 0.0)),
            "volume": int(float(raw.get("vol", raw.get("volume", 0)))),
            "amount": float(raw.get("amount", 0.0)),
        }

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        raise ValueError(f"Unsupported datetime value: {value!r}")

    @staticmethod
    def _map_exception(action: str, exc: Exception) -> RuntimeError:
        message = str(exc).lower()
        if "429" in message or "too many" in message or "rate" in message:
            return RuntimeError(f"{action} failed: rate limit")
        if "timeout" in message or "network" in message or "connection" in message:
            return RuntimeError(f"{action} failed: network error")
        if "no data" in message or "empty" in message:
            return RuntimeError(f"{action} failed: no data")
        return RuntimeError(f"{action} failed")
