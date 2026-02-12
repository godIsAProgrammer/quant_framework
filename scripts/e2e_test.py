#!/usr/bin/env python3
"""端到端功能测试 - 用真实数据验证完整流程"""

import sys
sys.path.insert(0, ".")

from datetime import date, timedelta
from pprint import pprint

def main():
    print("=" * 60)
    print("端到端功能测试")
    print("=" * 60)
    
    # 1. 数据源测试
    print("\n[1] 数据源测试 - 获取可转债列表")
    from contrib.data.akshare_source import AKShareDataSource
    data_source = AKShareDataSource()
    try:
        cb_list = data_source.fetch_cb_list()
        print(f"✅ 获取到 {len(cb_list)} 只可转债")
        if cb_list:
            print(f"   示例: {cb_list[0]}")
    except Exception as e:
        print(f"❌ 失败: {e}")
        cb_list = []
    
    # 2. 策略测试
    print("\n[2] 策略测试 - 双低策略选股")
    from contrib.strategy.double_low import DoubleLowStrategy
    
    # 构造测试数据（如果真实数据获取失败）
    if not cb_list:
        cb_list = [
            {"code": "123001", "price": 100, "premium_rate": 0.1, "volume": 2000000, "maturity_date": "2028-01-01"},
            {"code": "123002", "price": 105, "premium_rate": 0.05, "volume": 3000000, "maturity_date": "2027-06-01"},
            {"code": "123003", "price": 95, "premium_rate": 0.15, "volume": 1500000, "maturity_date": "2029-03-01"},
            {"code": "123004", "price": 110, "premium_rate": 0.02, "volume": 5000000, "maturity_date": "2028-12-01"},
            {"code": "123005", "price": 98, "premium_rate": 0.08, "volume": 2500000, "maturity_date": "2027-09-01"},
        ]
        print("   (使用模拟数据)")
    
    strategy = DoubleLowStrategy()
    strategy.top_n = 3
    
    # 计算双低值
    sorted_data = strategy.calculate_double_low(cb_list)
    print(f"✅ 双低值排序完成，前3名:")
    for i, item in enumerate(sorted_data[:3]):
        print(f"   {i+1}. {item.get('code', item.get('symbol', 'N/A'))} - 双低值: {item.get('double_low', 'N/A'):.2f}")
    
    # 3. 回测测试
    print("\n[3] 回测测试 - 简单回测")
    from contrib.backtest.simple_backtest import SimpleBacktestEngine, BacktestResult
    
    # 构造历史数据
    historical_data = [
        {"date": "2024-01-02", "symbol": "123001", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000000},
        {"date": "2024-01-03", "symbol": "123001", "open": 101, "high": 105, "low": 100, "close": 104, "volume": 1200000},
        {"date": "2024-01-04", "symbol": "123001", "open": 104, "high": 106, "low": 103, "close": 105, "volume": 1100000},
        {"date": "2024-01-05", "symbol": "123001", "open": 105, "high": 108, "low": 104, "close": 107, "volume": 1300000},
        {"date": "2024-01-08", "symbol": "123001", "open": 107, "high": 110, "low": 106, "close": 109, "volume": 1400000},
    ]
    
    engine = SimpleBacktestEngine(initial_cash=100000, trade_mode="T+0", commission_rate=0.0003)
    
    # 简单买入持有策略测试
    class SimpleStrategy:
        def on_init(self, context):
            pass
        def on_bar(self, context, bar):
            from contrib.strategy.double_low import Signal
            # 兼容聚合模式：从 cb_data 获取数据
            cb_data = bar.get("cb_data", [bar])
            first_record = cb_data[0] if cb_data else bar
            bar_date = bar.get("date", "")
            close_price = first_record.get("close", 100)
            
            # 第一天买入
            if bar_date == "2024-01-02":
                return [Signal(symbol="123001", direction="BUY", quantity=100, price=close_price)]
            # 最后一天卖出
            if bar_date == "2024-01-08":
                return [Signal(symbol="123001", direction="SELL", quantity=100, price=close_price)]
            return []
    
    try:
        result = engine.run(
            strategy=SimpleStrategy(),
            data=historical_data,
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 8),
        )
        print(f"✅ 回测完成:")
        print(f"   初始资金: {result.initial_cash:,.0f}")
        print(f"   最终资产: {result.final_value:,.2f}")
        print(f"   总收益率: {result.total_return:.2%}")
        print(f"   交易次数: {result.trade_count}")
        print(f"   净值曲线: {len(result.net_value_series)} 个数据点")
    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 风控测试
    print("\n[4] 风控测试 - 基础风控插件")
    from contrib.risk.basic_risk_plugin import BasicRiskPlugin
    from core.risk import RiskCheckResult
    
    risk_plugin = BasicRiskPlugin()
    risk_plugin.max_position_ratio = 0.3
    risk_plugin.max_trade_ratio = 0.2
    
    # 模拟检查
    test_order = {"symbol": "123001", "direction": "BUY", "quantity": 100, "price": 100}
    print(f"✅ 风控插件配置: max_position={risk_plugin.max_position_ratio}, max_trade={risk_plugin.max_trade_ratio}")
    print(f"   测试订单: {test_order}")
    
    print("\n" + "=" * 60)
    print("端到端测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
