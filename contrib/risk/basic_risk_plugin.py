"""Basic risk plugin implementation."""

from __future__ import annotations

from typing import Any

from core.context import Context
from core.risk import RiskCheckResult
from plugins.base import Plugin


class BasicRiskPlugin(Plugin):
    """基础风控插件。

    规则：
    - 最大仓位比例：单只股票不超过总资产指定比例
    - 单笔交易金额：不超过可用资金指定比例
    """

    name = "basic_risk"
    version = "1.0.0"

    max_position_ratio: float = 0.3
    max_trade_ratio: float = 0.2

    def __init__(
        self,
        max_position_ratio: float | None = None,
        max_trade_ratio: float | None = None,
    ) -> None:
        super().__init__()
        if max_position_ratio is not None:
            self.max_position_ratio = max_position_ratio
        if max_trade_ratio is not None:
            self.max_trade_ratio = max_trade_ratio

    def setup(self, context: Context) -> None:
        _ = context

    def teardown(self, context: Context) -> None:
        _ = context

    def check_order(self, order: dict[str, Any], context: Context) -> RiskCheckResult:
        side = str(order.get("side", "BUY")).upper()
        if side != "BUY":
            return RiskCheckResult(passed=True)

        symbol = str(order.get("symbol", ""))
        quantity = int(order.get("quantity", 0) or 0)
        price = float(order.get("price", 0.0) or 0.0)

        if not symbol or quantity <= 0 or price <= 0:
            return RiskCheckResult(
                passed=False,
                violations=["Invalid order fields for risk check"],
            )

        violations: list[str] = []

        trade_amount = quantity * price
        max_trade_amount = context.portfolio.cash * self.max_trade_ratio
        if trade_amount > max_trade_amount:
            violations.append(
                f"Trade amount violation: {trade_amount:.2f} > limit {max_trade_amount:.2f}"
            )

        total_assets = context.portfolio.get_total_value({symbol: price})
        if total_assets > 0:
            position = context.portfolio.get_position(symbol)
            current_qty = position.quantity if position is not None else 0
            projected_value = (current_qty + quantity) * price
            position_ratio = projected_value / total_assets
            if position_ratio > self.max_position_ratio:
                violations.append(
                    f"Position ratio violation: {position_ratio:.2%} > limit {self.max_position_ratio:.2%}"
                )

        return RiskCheckResult(passed=len(violations) == 0, violations=violations)

    def on_order(
        self, context: Context, order: dict[str, Any]
    ) -> dict[str, Any] | None:
        result = self.check_order(order, context)
        if result.passed:
            return order

        context.logger.warning(
            "Order blocked by basic_risk: %s", "; ".join(result.violations)
        )
        return None
