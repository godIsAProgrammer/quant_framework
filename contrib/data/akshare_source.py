"""AKShare data source plugin.

This module provides a built-in data source plugin backed by AKShare for
convertible bonds and A-share daily bars.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from core.cache import CacheManager, MemoryCache
from core.context import Context
from plugins.base import Plugin

try:
    import akshare as ak
except ImportError:  # pragma: no cover - tests patch module-level ak directly
    ak = None


class AKShareDataSource(Plugin):
    """AKShare 数据源插件，支持可转债和 A 股数据。"""

    name = "akshare"
    version = "1.0.0"
    description = "AKShare data source for convertible bonds and A-shares"

    def __init__(self) -> None:
        """Initialize plugin and cache manager."""
        super().__init__()
        self._cache = CacheManager(MemoryCache())
        self._context: Context | None = None

    def setup(self, context: Context) -> None:
        """Bind runtime context for this plugin instance."""
        self._context = context

    def teardown(self, context: Context) -> None:
        """Release runtime context references."""
        _ = context
        self._context = None

    def _ak(self) -> Any:
        """Return AKShare module or raise clear runtime error when unavailable."""
        if ak is None:
            raise RuntimeError("akshare is not installed")
        return ak

    def fetch_cb_list(self) -> list[dict[str, Any]]:
        """Fetch convertible bond list."""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._ak().bond_zh_cov()
                return self._to_records(frame)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("fetch_cb_list failed") from exc

        key = self._cache.cache_key("cb_list")
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=60.0)
        )

    def fetch_cb_realtime(self, codes: list[str]) -> list[dict[str, Any]]:
        """Fetch realtime quotes for convertible bonds."""
        try:
            frame = self._ak().bond_zh_hs_cov_spot()
            rows = self._to_records(frame)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("fetch_cb_realtime failed") from exc

        if not codes:
            return rows

        code_set = set(codes)
        return [row for row in rows if str(row.get("代码", "")) in code_set]

    def fetch_cb_history(
        self,
        code: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """Fetch normalized historical daily bars for one convertible bond."""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._ak().bond_zh_hs_cov_daily(symbol=code)
                rows = self._to_records(frame)
                normalized = [self._normalize_bar(row, symbol=code) for row in rows]
                return [
                    bar
                    for bar in normalized
                    if start <= cast(datetime, bar.get("datetime")).date() <= end
                ]
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("fetch_cb_history failed") from exc

        key = self._cache.cache_key("cb_history", code, start, end)
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=60.0)
        )

    def fetch_stock_daily(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """Fetch normalized A-share historical daily bars."""

        def _factory() -> list[dict[str, Any]]:
            try:
                frame = self._ak().stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="",
                )
                rows = self._to_records(frame)
                return [self._normalize_bar(row, symbol=symbol) for row in rows]
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("fetch_stock_daily failed") from exc

        key = self._cache.cache_key("stock_daily", symbol, start, end)
        return cast(
            list[dict[str, Any]], self._cache.get_or_set(key, _factory, ttl=60.0)
        )

    def _normalize_bar(self, raw: dict[str, Any], symbol: str) -> dict[str, Any]:
        """Normalize raw bar payload to framework standard format."""
        dt_value = raw.get("日期") or raw.get("datetime") or raw.get("date")
        dt = self._parse_datetime(dt_value)

        amount_raw = raw.get("成交额", raw.get("amount", 0.0))

        return {
            "symbol": symbol,
            "datetime": dt,
            "open": float(raw.get("开盘", raw.get("open", 0.0))),
            "high": float(raw.get("最高", raw.get("high", 0.0))),
            "low": float(raw.get("最低", raw.get("low", 0.0))),
            "close": float(raw.get("收盘", raw.get("close", 0.0))),
            "volume": int(float(raw.get("成交量", raw.get("volume", 0)))),
            "amount": float(amount_raw or 0.0),
        }

    @staticmethod
    def _to_records(frame: Any) -> list[dict[str, Any]]:
        """Convert a DataFrame-like object to list[dict]."""
        if hasattr(frame, "to_dict"):
            records = frame.to_dict(orient="records")
            if isinstance(records, list):
                return [dict(item) for item in records]
        return []

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        """Parse date/datetime values into ``datetime``."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        raise ValueError(f"Unsupported datetime value: {value!r}")
