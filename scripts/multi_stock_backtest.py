"""
多股票批量回測
對 watchlist 所有股票跑同一策略，找出「策略在哪些標的真的有優勢」
用法：py scripts/multi_stock_backtest.py --strategy ma_filtered --start 2022-01-01 --end 2024-01-01
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from rich.console import Console
from rich.table import Table
from data.fetcher import fetch_daily_ohlcv
from backtest.runner import run_backtest
from strategy import STRATEGIES
from scripts.daily_scan import load_watchlist

console = Console()


def multi_stock_backtest(
    strategy_name: str = "ma_filtered",
    start: str = "2022-01-01",
    end: str = "2024-01-01",
    min_trades: int = 3,          # 交易次數太少不算數
) -> pd.DataFrame:

    strategy_cls = STRATEGIES.get(strategy_name)
    if not strategy_cls:
        console.print(f"[red]未知策略: {strategy_name}，可用: {list(STRATEGIES.keys())}[/red]")
        return pd.DataFrame()

    watchlist = load_watchlist()
    console.print(
        f"\n[bold cyan]多股票批量回測[/bold cyan]\n"
        f"  策略: [yellow]{strategy_name}[/yellow]  "
        f"期間: {start} ~ {end}  "
        f"股票數: {len(watchlist)}\n"
    )

    results = []
    for stock in watchlist:
        sid = stock["id"]
        try:
            df = fetch_daily_ohlcv(sid, start, end, use_cache=True)
            if len(df) < 80:  # 資料不足就跳過
                continue
            m = run_backtest(strategy_cls, df, stock_id=sid, plot=False)
            m["name"] = stock["name"]
            if m["total_trades"] >= min_trades:  # 交易次數門檻
                results.append(m)
            else:
                console.print(f"[dim]{sid} 交易次數 {m['total_trades']} 次，跳過[/dim]")
        except Exception as e:
            console.print(f"[dim red]{sid} 失敗: {e}[/dim red]")

    if not results:
        console.print("[red]無有效結果[/red]")
        return pd.DataFrame()

    df_result = pd.DataFrame(results).sort_values("total_return_pct", ascending=False)
    _print_multi_results(df_result, strategy_name)
    _print_verdict(df_result)
    return df_result


def _print_multi_results(df: pd.DataFrame, strategy_name: str):
    table = Table(
        title=f"多股票回測總覽  策略={strategy_name}",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("代號",     style="cyan", width=6)
    table.add_column("名稱",                   width=10)
    table.add_column("報酬率%",  justify="right", width=9)
    table.add_column("夏普",     justify="right", width=9)
    table.add_column("最大回撤%",justify="right", width=10)
    table.add_column("勝率%",    justify="right", width=7)
    table.add_column("獲利因子", justify="right", width=9)
    table.add_column("交易數",   justify="right", width=7)

    for _, row in df.iterrows():
        col    = "green" if row["total_return_pct"] > 0 else "red"
        sharpe = f"{row['sharpe_ratio']:.3f}" if row.get("sharpe_ratio") else "N/A"
        table.add_row(
            row["stock_id"],
            row.get("name", ""),
            f"[{col}]{row['total_return_pct']:+.2f}[/{col}]",
            sharpe,
            f"{row['max_drawdown_pct']:.2f}",
            f"{row['win_rate_pct']:.1f}",
            f"{row['profit_factor']:.2f}",
            str(int(row["total_trades"])),
        )

    console.print(table)


def _print_verdict(df: pd.DataFrame):
    n       = len(df)
    pos     = (df["total_return_pct"] > 0).sum()
    pct     = pos / n * 100
    avg_ret = df["total_return_pct"].mean()

    console.print(
        f"\n正報酬股票：[{'green' if pos/n >= 0.5 else 'red'}]{pos}/{n} ({pct:.0f}%)[/{'green' if pos/n >= 0.5 else 'red'}]  "
        f"平均報酬：[{'green' if avg_ret >= 0 else 'red'}]{avg_ret:+.2f}%[/{'green' if avg_ret >= 0 else 'red'}]"
    )

    # 推薦清單：正報酬 + 夏普 > 0 + 交易次數 ≥ 5
    good = df[
        (df["total_return_pct"] > 0) &
        (df["win_rate_pct"] >= 40) &
        (df["total_trades"] >= 5)
    ]
    if not good.empty:
        console.print(f"\n[bold green]建議重點追蹤（正報酬 + 勝率≥40% + 交易數≥5）：[/bold green]")
        for _, r in good.iterrows():
            console.print(
                f"  [cyan]{r['stock_id']}[/cyan] {r['name']}  "
                f"報酬:{r['total_return_pct']:+.2f}%  "
                f"勝率:{r['win_rate_pct']:.1f}%  "
                f"交易:{int(r['total_trades'])}次"
            )
    else:
        console.print("\n[yellow]無股票同時滿足正報酬 + 勝率≥40% + 交易數≥5[/yellow]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="ma_filtered")
    parser.add_argument("--start",    default="2022-01-01")
    parser.add_argument("--end",      default="2024-01-01")
    parser.add_argument("--min-trades", type=int, default=3)
    args = parser.parse_args()
    multi_stock_backtest(args.strategy, args.start, args.end, args.min_trades)
