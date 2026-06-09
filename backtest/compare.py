"""多策略比較工具 — 同一股票同一時段，一次跑完所有策略"""
import pandas as pd
from rich.console import Console
from rich.table import Table
from .runner import run_backtest

console = Console()


def compare_strategies(
    strategies: dict,
    df: pd.DataFrame,
    stock_id: str = "stock",
    plot: bool = False,
) -> pd.DataFrame:
    """
    strategies: {"策略名稱": StrategyClass, ...}
    回傳各策略績效的 DataFrame，同時在 console 印出比較表。
    """
    results = []
    for name, cls in strategies.items():
        console.print(f"\n[dim]>>> 跑策略：{name}[/dim]")
        try:
            m = run_backtest(cls, df.copy(), stock_id=stock_id, plot=plot)
            m["strategy"] = name
            results.append(m)
        except Exception as e:
            console.print(f"[red]{name} 回測失敗: {e}[/red]")

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    _print_comparison(df_result)
    return df_result


def _print_comparison(df: pd.DataFrame):
    table = Table(
        title="策略比較總表",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("策略",     style="yellow", width=12)
    table.add_column("報酬率%",  justify="right", width=9)
    table.add_column("夏普比率", justify="right", width=9)
    table.add_column("最大回撤%",justify="right", width=10)
    table.add_column("勝率%",    justify="right", width=8)
    table.add_column("獲利因子", justify="right", width=9)
    table.add_column("交易次數", justify="right", width=9)

    df_sorted = df.sort_values("sharpe_ratio", ascending=False, na_position="last")

    for _, row in df_sorted.iterrows():
        ret = row["total_return_pct"]
        col = "green" if ret >= 0 else "red"
        sharpe = f"{row['sharpe_ratio']:.3f}" if row.get("sharpe_ratio") else "N/A"
        table.add_row(
            row["strategy"],
            f"[{col}]{ret:+.2f}[/{col}]",
            sharpe,
            f"{row['max_drawdown_pct']:.2f}",
            f"{row['win_rate_pct']:.1f}",
            f"{row['profit_factor']:.2f}",
            str(int(row["total_trades"])),
        )

    console.print("\n")
    console.print(table)
