#!/usr/bin/env python3
"""完整回测流程端到端测试 - 数据源→策略→回测→结果"""

import sys
sys.path.insert(0, ".")

from datetime import date, timedelta
from pprint import pprint


def main():
    print("=" * 60)
    print("完整回测流程端到端测试")
    print("=" * 60)

    # 1. 获取真实可转债数据
    print("\n[1] 获取可转债数据")
    from contrib.data.akshare_source import AKShareDataSource

    data_source = AKShareDataSource()
    try:
        cb_list = data_source.fetch_cb_list()
        print(f"✅ 获取到 {len(cb_list)} 只可转债")
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        # 使用模拟数据继续
        cb_list = []

    # 2. 准备回测数据（用模拟数据，因为历史数据获取较慢）
    print("\n[2] 准备回测历史数据")

    # 模拟 5 只可转债 10 天的数据
    symbols = ["123001", "123002", "123003", "123004", "123005"]
    base_prices = {"123001": 100, "123002": 105, "123003": 95, "123004": 110, "123005": 98}
    premium_rates = {"123001": 0.10, "123002": 0.05, "123003": 0.15, "123004": 0.02, "123005": 0.08}

    historical_data = []
    start_date = date(2024, 1, 2)

    import random
    random.seed(42)  # 可重复

    for day_offset in range(10):
        current_date = start_date + timedelta(days=day_offset)
        if current_date.weekday() >= 5:  # 跳过周末
            continue

        cb_snapshot = []
        for symbol in symbols:
            base = base_prices[symbol]
            # 模拟价格波动
            change = random.uniform(-0.02, 0.03)
            close_price = base * (1 + change * (day_offset + 1))

            bar = {
                "date": current_date.isoformat(),
                "symbol": symbol,
                "code": symbol,
                "price": close_price,
                "open": close_price * 0.99,
                "high": close_price * 1.01,
                "low": close_price * 0.98,
                "close": close_price,
                "volume": random.randint(1000000, 5000000),
                "premium_rate": premium_rates[symbol],
                "maturity_date": "2028-01-01",
            }
            historical_data.append(bar)
            cb_snapshot.append(bar)

    print(f"✅ 生成 {len(historical_data)} 条历史数据")

    # 3. 初始化策略
    print("\n[3] 初始化双低策略")
    from contrib.strategy.double_low import DoubleLowStrategy

    strategy = DoubleLowStrategy()
    strategy.top_n = 3
    strategy.min_volume = 500000
    strategy.rebalance_days = 3
    print(f"✅ 策略配置: top_n={strategy.top_n}, rebalance_days={strategy.rebalance_days}")

    # 4. 初始化回测引擎
    print("\n[4] 初始化回测引擎")
    from contrib.backtest.simple_backtest import SimpleBacktestEngine

    engine = SimpleBacktestEngine(
        initial_cash=100000,
        trade_mode="T+0",
        commission_rate=0.0003,
        slippage=0.001,
    )
    print("✅ 回测引擎配置: initial_cash=100000, T+0, commission=0.03%")

    # 5. 初始化风控
    print("\n[5] 初始化风控插件")
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin

    risk_plugin = BasicRiskPlugin()
    risk_plugin.max_position_ratio = 0.4
    risk_plugin.max_trade_ratio = 0.3
    print(f"✅ 风控配置: max_position={risk_plugin.max_position_ratio}, max_trade={risk_plugin.max_trade_ratio}")

    # 6. 运行回测
    print("\n[6] 运行回测")

    try:
        result = engine.run(
            strategy=strategy,
            data=historical_data,
            start_date=start_date,
            end_date=start_date + timedelta(days=14),
        )

        print("✅ 回测完成!")
        print(f"\n{'='*40}")
        print("回测结果汇总")
        print(f"{'='*40}")
        print(f"  初始资金:   {result.initial_cash:>12,.0f}")
        print(f"  最终资产:   {result.final_value:>12,.2f}")
        print(f"  总收益率:   {result.total_return:>12.2%}")
        print(f"  年化收益:   {result.annual_return:>12.2%}")
        print(f"  夏普比率:   {result.sharpe_ratio:>12.2f}")
        print(f"  最大回撤:   {result.max_drawdown:>12.2%}")
        print(f"  胜率:       {result.win_rate:>12.2%}")
        print(f"  交易次数:   {result.trade_count:>12}")
        print(f"  净值点数:   {len(result.net_value_series):>12}")

        if result.trades:
            print("\n交易记录 (前5笔):")
            for i, trade in enumerate(result.trades[:5]):
                print(f"  {i+1}. {trade}")

    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("完整回测流程测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
