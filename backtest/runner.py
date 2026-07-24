"""Backtrader 回測執行器"""
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from strategy.base import TwStockCommission
from config import INITIAL_CAPITAL, SLIPPAGE


def run_backtest(
    strategy_cls,
    df: pd.DataFrame,
    stock_id: str = "stock",
    cash: float = INITIAL_CAPITAL,
    plot: bool = True,
    strategy_params: dict = None,
    extra_data: dict = None,      # {"market": df_0050} → 大盤過濾用
    verbose: bool = True,
) -> dict:
    """
    執行回測並回傳績效指標。

    df 欄位需包含：date, open, high, low, close, volume
    extra_data: 額外資料流，key 為名稱，value 為 DataFrame（同格式）
    """
    cerebro = bt.Cerebro()

    # 載入主資料
    data_feed = bt.feeds.PandasData(
        dataname=df.set_index("date"),
        name=stock_id,
    )
    cerebro.adddata(data_feed)

    # 載入額外資料（大盤等）
    if extra_data:
        for name, edf in extra_data.items():
            feed = bt.feeds.PandasData(
                dataname=edf.set_index("date"),
                name=name,
            )
            cerebro.adddata(feed)

    # 加入策略
    if strategy_params:
        cerebro.addstrategy(strategy_cls, **strategy_params)
    else:
        cerebro.addstrategy(strategy_cls)

    # 手續費
    cerebro.broker.addcommissioninfo(TwStockCommission(), name=stock_id)

    # 滑價
    cerebro.broker.set_slippage_perc(SLIPPAGE)

    # 初始資金
    cerebro.broker.setcash(cash)

    # 分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    if verbose:
        print(f"\n{'='*50}")
        print(f"開始回測：{stock_id}  初始資金：{cash:,.0f}")
        print(f"{'='*50}")

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = (final_value - cash) / cash * 100

    # 整理績效
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio", None)
    dd = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    won = trades.get("won", {}).get("total", 0)
    lost = trades.get("lost", {}).get("total", 0)
    total_trades = won + lost
    win_rate = won / total_trades * 100 if total_trades > 0 else 0

    avg_win = trades.get("won", {}).get("pnl", {}).get("average", 0)
    avg_loss = trades.get("lost", {}).get("pnl", {}).get("average", 0)

    # 獲利因子 = 總獲利 / 總虧損（非平均值比，平均值比是「賺賠比」）
    won_total  = trades.get("won", {}).get("pnl", {}).get("total", 0)
    lost_total = trades.get("lost", {}).get("pnl", {}).get("total", 0)
    if lost_total:
        profit_factor = abs(won_total / lost_total)
    else:
        profit_factor = float("inf") if won_total else 0.0

    metrics = {
        "stock_id": stock_id,
        "initial_capital": cash,
        "final_value": final_value,
        "total_return_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown_pct": round(dd.get("max", {}).get("drawdown", 0), 2),
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else float("inf"),
    }

    if verbose:
        _print_metrics(metrics)

    if plot:
        cerebro.plot(style="candlestick", barup="red", bardown="green")

    return metrics


def _print_metrics(m: dict):
    print(f"\n{'─'*50}")
    print(f"  最終資金：   {m['final_value']:>12,.0f}")
    print(f"  總報酬率：   {m['total_return_pct']:>11.2f}%")
    print(f"  夏普比率：   {m['sharpe_ratio']}")
    print(f"  最大回撤：   {m['max_drawdown_pct']:>11.2f}%")
    print(f"  交易次數：   {m['total_trades']:>12}")
    print(f"  勝率：       {m['win_rate_pct']:>11.1f}%")
    print(f"  平均獲利：   {m['avg_win']:>12.0f}")
    print(f"  平均虧損：   {m['avg_loss']:>12.0f}")
    print(f"  獲利因子：   {m['profit_factor']}")
    print(f"{'─'*50}\n")
