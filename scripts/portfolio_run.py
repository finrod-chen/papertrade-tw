"""
一鍵投資組合回測腳本
- 自動讀取 data/optimal_params.json（若有），否則用預設參數
- 用法：py scripts/portfolio_run.py [--strategy ma_filtered] [--use-optimal]
"""
import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from data.fetcher import fetch_daily_ohlcv
from backtest.portfolio import portfolio_backtest, load_stock_dfs
from strategy import STRATEGIES
from scripts.daily_scan import load_watchlist
from scripts.per_stock_optimize import PARAMS_PATH, load_optimal
from rich.console import Console

console = Console()


def run(strategy_name: str = "ma_filtered",
        start: str = "2020-01-01",
        end:   str = "2024-01-01",
        use_optimal: bool = True,
        use_market: bool = True,
        total_capital: float = 3_600_000):  # 18支×200K 讓台積電也能買1張


    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        console.print(f"[red]未知策略: {strategy_name}[/red]")
        return

    watchlist  = load_watchlist()
    console.print(f"[cyan]載入 {len(watchlist)} 支股票資料...[/cyan]")
    stock_dfs, names = load_stock_dfs(watchlist, start, end)

    # 讀取每股最佳參數
    per_stock_params = None
    if use_optimal and os.path.exists(PARAMS_PATH):
        optimal = load_optimal()
        per_stock_params = {sid: v["params"] for sid, v in optimal.items() if sid in stock_dfs}
        covered = len([s for s in stock_dfs if s in per_stock_params])
        console.print(f"[green]{covered}/{len(stock_dfs)} 支使用個別最佳參數[/green]")
    else:
        console.print("[yellow]使用預設參數（未找到 optimal_params.json）[/yellow]")

    # 大盤過濾
    extra_data = None
    if use_market and "0050" in stock_dfs:
        extra_data = {"market": stock_dfs["0050"]}
        console.print("[cyan]大盤過濾：啟用 (0050 MA20)[/cyan]")

    result = portfolio_backtest(
        strategy_cls     = strategy_cls,
        stock_dfs        = stock_dfs,
        names            = names,
        total_capital    = total_capital,
        per_stock_params = per_stock_params,
        extra_data       = extra_data,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy",    default="ma_filtered")
    parser.add_argument("--start",       default="2020-01-01")
    parser.add_argument("--end",         default="2024-01-01")
    parser.add_argument("--use-optimal", action="store_true", default=True)
    parser.add_argument("--no-market",   action="store_true")
    args = parser.parse_args()

    run(
        strategy_name = args.strategy,
        start         = args.start,
        end           = args.end,
        use_optimal   = args.use_optimal,
        use_market    = not args.no_market,
    )
