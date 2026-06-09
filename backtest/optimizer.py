"""
參數網格搜索
對策略的所有參數組合做回測，找出最佳參數，
再用 Walk-Forward 驗證最佳參數是否真的穩健。
"""
import itertools
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from .runner import run_backtest

console = Console()


def grid_search(
    strategy_cls,
    df: pd.DataFrame,
    param_grid: dict,
    stock_id: str = "stock",
    metric: str = "sharpe_ratio",
    top_n: int = 10,
) -> pd.DataFrame:
    """
    網格搜索最佳參數。

    param_grid 範例：
        {
            "fast_period": [3, 5, 8],
            "slow_period": [15, 20, 30],
        }

    metric 優化目標（值越大越好）：
        "sharpe_ratio" | "total_return_pct" | "win_rate_pct" | "profit_factor"
    特殊：metric = "max_drawdown_pct" → 越小越好
    """
    keys   = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))

    console.print(
        f"\n[bold cyan]參數網格搜索[/bold cyan]  "
        f"共 {len(combos)} 組合  優化目標: {metric}"
    )

    results = []
    for i, combo in enumerate(combos, 1):
        params = dict(zip(keys, combo))
        try:
            m = run_backtest(
                strategy_cls, df.copy(),
                stock_id=stock_id, plot=False,
                strategy_params=params,
            )
            m["params"] = str(params)
            for k, v in params.items():
                m[k] = v
            results.append(m)
        except Exception as e:
            console.print(f"[dim red]  {params} → 失敗: {e}[/dim red]")

        if i % 10 == 0:
            console.print(f"[dim]  進度 {i}/{len(combos)}...[/dim]")

    if not results:
        console.print("[red]沒有任何組合成功[/red]")
        return pd.DataFrame()

    df_res = pd.DataFrame(results)

    # 排序
    ascending = (metric == "max_drawdown_pct")
    df_sorted = df_res.sort_values(metric, ascending=ascending, na_position="last")

    _print_grid_table(df_sorted, keys, metric, top_n)
    return df_sorted


def _print_grid_table(df: pd.DataFrame, param_keys: list, metric: str, top_n: int):
    table = Table(
        title=f"網格搜索 Top {top_n}（依 {metric} 排序）",
        header_style="bold cyan",
        show_lines=True,
    )
    for k in param_keys:
        table.add_column(k, justify="center", width=8)

    table.add_column("報酬率%",   justify="right", width=9)
    table.add_column("夏普",      justify="right", width=9)
    table.add_column("最大回撤%", justify="right", width=10)
    table.add_column("勝率%",     justify="right", width=7)
    table.add_column("交易數",    justify="right", width=7)

    for _, row in df.head(top_n).iterrows():
        col    = "green" if row["total_return_pct"] > 0 else "red"
        sharpe = f"{row['sharpe_ratio']:.3f}" if row.get("sharpe_ratio") else "N/A"
        table.add_row(
            *[str(row[k]) for k in param_keys],
            f"[{col}]{row['total_return_pct']:+.2f}[/{col}]",
            sharpe,
            f"{row['max_drawdown_pct']:.2f}",
            f"{row['win_rate_pct']:.1f}",
            str(int(row["total_trades"])),
        )

    console.print(table)

    best = df.iloc[0]
    console.print(
        f"\n[bold green]最佳參數：[/bold green]{best['params']}\n"
        f"  報酬率: {best['total_return_pct']:+.2f}%  "
        f"夏普: {best.get('sharpe_ratio')}  "
        f"勝率: {best['win_rate_pct']:.1f}%  "
        f"最大回撤: {best['max_drawdown_pct']:.2f}%"
    )
