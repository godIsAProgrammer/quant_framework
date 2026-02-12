"""Simple backtest engine plugin."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from core.config import FrameworkConfig
from core.context import Context
from core.engine import EventEngine
from core.portfolio import Portfolio
from core.risk import RiskManager
from plugins.base import Plugin
from plugins.protocols import StrategyProtocol


@dataclass
class BacktestResult:
    """回测结果。"""

    initial_cash: float
    final_value: float
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    net_value_series: list[dict[str, Any]]
    trades: list[dict[str, Any]]


class SimpleBacktestEngine(Plugin):
    """简单回测引擎。

    功能：
    - 加载历史数据
    - 按时间顺序回放
    - 订单撮合（市价/限价）
    - 手续费计算
    - 统计指标计算
    """

    name = "simple_backtest"
    version = "1.0.0"

    def __init__(
        self,
        initial_cash: float = 100_000,
        trade_mode: Literal["T+0", "T+1"] = "T+0",
        commission_rate: float = 0.0003,
        slippage: float = 0.001,
    ) -> None:
        super().__init__()
        self.initial_cash = float(initial_cash)
        self.trade_mode = trade_mode
        self.commission_rate = float(commission_rate)
        self.slippage = float(slippage)

        self._context: Context | None = None
        self._strategy: StrategyProtocol | None = None
        self._portfolio: Portfolio | None = None

        self._latest_prices: dict[str, float] = {}
        self._trades: list[dict[str, Any]] = []
        self._net_value_series: list[dict[str, Any]] = []

    def setup(self, context: Context) -> None:
        """Bind runtime context for this engine."""
        self._context = context

    def teardown(self, context: Context) -> None:
        """Release runtime context reference."""
        _ = context
        self._context = None

    def run(
        self,
        strategy: StrategyProtocol,
        data: list[dict[str, Any]],
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        """Run backtest in [start_date, end_date]."""
        from collections import defaultdict

        self._strategy = strategy
        self._portfolio = Portfolio(
            initial_cash=self.initial_cash, trade_mode=self.trade_mode
        )
        self._latest_prices = {}
        self._trades = []
        self._net_value_series = []

        context = Context(
            config=FrameworkConfig(),
            portfolio=self._portfolio,
            risk_manager=RiskManager(),
            event_engine=EventEngine(),
            logger=logging.getLogger("backtest.simple"),
        )
        self.setup(context)

        if hasattr(strategy, "on_init"):
            strategy.on_init(context)

        # 按日期聚合数据
        daily_bars: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for bar in data:
            bar_date = self._coerce_date(bar.get("date"))
            if start_date <= bar_date <= end_date:
                daily_bars[bar_date].append(bar)

        # 按日期顺序处理
        for bar_date in sorted(daily_bars.keys()):
            day_bars = daily_bars[bar_date]

            # 更新最新价格
            for bar in day_bars:
                symbol = str(bar.get("symbol", ""))
                if symbol:
                    self._latest_prices[symbol] = float(bar.get("close", 0.0) or 0.0)

            # 构造聚合 bar，包含 cb_data
            aggregated_bar: dict[str, Any] = {
                "date": bar_date.isoformat(),
                "cb_data": day_bars,
            }

            # 调用策略处理
            self._process_bar(aggregated_bar)

            # T+1 日结算
            if self.trade_mode == "T+1":
                self._portfolio.settle_day(bar_date)

        result = self._calculate_stats()
        self.teardown(context)
        return result

    def _process_bar(self, bar: dict[str, Any]) -> None:
        """Process one bar: strategy signal -> order match -> account update."""
        if self._context is None or self._portfolio is None or self._strategy is None:
            raise RuntimeError("engine not initialized")

        bar_date = self._coerce_date(bar.get("date"))

        raw_signals = self._strategy.on_bar(self._context, bar)
        orders = self._normalize_orders(raw_signals)

        for order in orders:
            # 使用 _latest_prices 撮合，不依赖单条 bar
            trade = self._match_order_v2(order, bar_date)
            if trade is None:
                continue

            amount = float(trade["amount"])
            commission = self._calculate_commission(amount)

            side = str(trade["side"])
            if side == "BUY":
                if amount + commission > self._portfolio.cash:
                    continue
                self._portfolio.buy(
                    symbol=str(trade["symbol"]),
                    quantity=int(trade["quantity"]),
                    price=float(trade["price"]),
                    date=bar_date,
                )
                self._portfolio.cash -= commission
                trade["commission"] = commission
                trade["pnl"] = 0.0
                self._trades.append(trade)
                continue

            try:
                realized_pnl = self._portfolio.sell(
                    symbol=str(trade["symbol"]),
                    quantity=int(trade["quantity"]),
                    price=float(trade["price"]),
                    date=bar_date,
                )
            except ValueError:
                continue

            self._portfolio.cash -= commission
            trade["commission"] = commission
            trade["pnl"] = realized_pnl - commission
            self._trades.append(trade)

        self._portfolio.settle_day(bar_date)

        value = self._portfolio.get_total_value(self._latest_prices)
        self._net_value_series.append({"date": bar_date, "value": value})

    def _match_order_v2(
        self, order: dict[str, Any], bar_date: date
    ) -> dict[str, Any] | None:
        """Match order using latest prices (for aggregated bar mode)."""
        symbol = str(order.get("symbol", ""))
        if not symbol:
            return None

        side = str(order.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            return None

        # 从最新价格获取
        close_price = self._latest_prices.get(symbol, 0.0)
        if close_price <= 0:
            return None

        # 处理 quantity=None 的情况（计算合适的数量）
        quantity = order.get("quantity")
        if quantity is None or quantity <= 0:
            if side == "BUY" and self._portfolio:
                # 买入：用可用资金的 1/N 计算（N=top_n）
                available = self._portfolio.cash * 0.3  # 每只最多 30%
                quantity = int(available / close_price)
            elif side == "SELL" and self._portfolio:
                # 卖出：全仓卖出
                pos = self._portfolio.get_position(symbol)
                quantity = pos.quantity if pos else 0

        quantity = int(quantity or 0)
        if quantity <= 0:
            return None

        # 计算成交价（含滑点）
        if side == "BUY":
            trade_price = close_price * (1 + self.slippage)
        else:
            trade_price = close_price * (1 - self.slippage)

        amount = trade_price * quantity
        return {
            "date": bar_date,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": trade_price,
            "amount": amount,
        }

    def _match_order(
        self, order: dict[str, Any], bar: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Match one order against current bar."""
        symbol = str(order.get("symbol", ""))
        if symbol != str(bar.get("symbol", "")):
            return None

        side = str(order.get("side", "")).upper()
        quantity = int(order.get("quantity", 0) or 0)
        if side not in {"BUY", "SELL"} or quantity <= 0:
            return None

        order_type = str(order.get("order_type", "MARKET")).upper()
        close_price = float(bar.get("close", 0.0) or 0.0)
        if close_price <= 0:
            return None

        trade_price: float
        if order_type == "MARKET":
            if side == "BUY":
                trade_price = close_price * (1 + self.slippage)
            else:
                trade_price = close_price * (1 - self.slippage)
        elif order_type == "LIMIT":
            limit_price = float(order.get("price", 0.0) or 0.0)
            if limit_price <= 0:
                return None

            low = float(bar.get("low", close_price) or close_price)
            high = float(bar.get("high", close_price) or close_price)
            if side == "BUY" and low <= limit_price:
                trade_price = limit_price
            elif side == "SELL" and high >= limit_price:
                trade_price = limit_price
            else:
                return None
        else:
            return None

        trade_date = self._coerce_date(bar.get("date"))
        amount = trade_price * quantity
        return {
            "date": trade_date,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": trade_price,
            "amount": amount,
        }

    def _calculate_commission(self, amount: float) -> float:
        """Calculate commission by transaction amount."""
        return float(amount) * self.commission_rate

    def _calculate_stats(self) -> BacktestResult:
        """Calculate backtest statistics from account curve and trades."""
        if not self._net_value_series:
            return BacktestResult(
                initial_cash=self.initial_cash,
                final_value=self.initial_cash,
                total_return=0.0,
                annual_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                trade_count=0,
                net_value_series=[],
                trades=[],
            )

        values = [float(item["value"]) for item in self._net_value_series]
        final_value = values[-1]
        total_return = (final_value - self.initial_cash) / self.initial_cash

        # 计算天数（兼容 date 对象和字符串）
        first_date = self._net_value_series[0]["date"]
        last_date = self._net_value_series[-1]["date"]
        if isinstance(first_date, str):
            first_date = self._coerce_date(first_date)
        if isinstance(last_date, str):
            last_date = self._coerce_date(last_date)
        days = max((last_date - first_date).days, 1)
        annual_return = (1 + total_return) ** (365 / days) - 1

        daily_returns: list[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if prev > 0:
                daily_returns.append(curr / prev - 1)

        sharpe_ratio = 0.0
        if daily_returns:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(
                daily_returns
            )
            std = math.sqrt(variance)
            if std > 0:
                sharpe_ratio = mean_ret / std * math.sqrt(252)

        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        sell_trades = [trade for trade in self._trades if trade.get("side") == "SELL"]
        wins = [trade for trade in sell_trades if float(trade.get("pnl", 0.0)) > 0]
        win_rate = (len(wins) / len(sell_trades)) if sell_trades else 0.0

        return BacktestResult(
            initial_cash=self.initial_cash,
            final_value=final_value,
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trade_count=len(self._trades),
            net_value_series=list(self._net_value_series),
            trades=list(self._trades),
        )

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Unsupported date value: {value!r}")

    @staticmethod
    def _normalize_orders(raw_signals: Any) -> list[dict[str, Any]]:
        if raw_signals is None:
            return []
        if not isinstance(raw_signals, list):
            return []

        orders: list[dict[str, Any]] = []
        for signal in raw_signals:
            if isinstance(signal, dict):
                symbol = str(signal.get("symbol", ""))
                side = str(signal.get("side", signal.get("direction", ""))).upper()
                quantity = int(signal.get("quantity", 1) or 1)
                order_type = str(signal.get("order_type", "")).upper()
                price = signal.get("price")
            else:
                symbol = str(getattr(signal, "symbol", ""))
                side = str(
                    getattr(signal, "side", getattr(signal, "direction", ""))
                ).upper()
                quantity = int(getattr(signal, "quantity", 1) or 1)
                order_type = str(getattr(signal, "order_type", "")).upper()
                price = getattr(signal, "price", None)

            if not order_type:
                order_type = "LIMIT" if price is not None else "MARKET"

            order: dict[str, Any] = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
            }
            if price is not None:
                order["price"] = float(price)

            orders.append(order)

        return orders
