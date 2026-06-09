"""
Walk-Forward 測試框架
目的：確認策略不是在特定歷史過擬合，而是真的有普遍優勢

原理：
  把完整資料切成 N 個滾動視窗
  每個視窗：[─── 訓練期 ───][─ OOS 測試期 ─]
  測試只看樣本外（OOS）的績效

判定標準：
  - OOS 正報酬視窗 ≥ 60% → 策略具一致性
  - OOS 平均報酬 > 0      → 整體有優勢
  兩項都達標 → 策略穩健
"""
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from .runner import run_backtest

console = Console()


def walk_forward_test(
    strategy_cls,
    df: pd.DataFrame,
    stock_id: str = "stock",
    train_days: int = 252,   # 訓練期 ≈ 1 年
    test_days:  int = 63,    # 測試期 ≈ 1 季
    step_days:  int = 63,    # 每次滾動 ≈ 1 季
    plot: bool = False,
    strategy_params: dict = None,
) -> dict:
    """
    滾動 Walk-Forward 測試，回傳彙總績效字典。
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    total = len(df)

    # ── 切視窗 ────────────────────────────────────────────────────
    windows = []
    i = 0
    while i + train_days + test_days <= total:
        tr = df.iloc[i : i + train_days]
        te = df.iloc[i + train_days : i + train_days + test_days]
        windows.append({
            "window":      len(windows) + 1,
            "train_start": tr.iloc[0]["date"].strftime("%Y-%m-%d"),
            "train_end":   tr.iloc[-1]["date"].strftime("%Y-%m-%d"),
            "test_start":  te.iloc[0]["date"].strftime("%Y-%m-%d"),
            "test_end":    te.iloc[-1]["date"].strftime("%Y-%m-%d"),
            "train_df":    tr,
            "test_df":     te,
        })
        i += step_days

    if not windows:
        console.print(
            f"[red]資料不足（共 {total} 根 K 棒），"
            f"需要至少 {train_days + test_days} 根才能跑 Walk-Forward。[/red]"
        )
        return {}

    console.print(
        f"\n[bold cyan]Walk-Forward 測試  {stock_id}[/bold cyan]  "
        f"訓練:{train_days}天  OOS測試:{test_days}天  視窗數:{len(windows)}"
    )
    console.print(f"資料範圍：{df.iloc[0]['date'].date()} ~ {df.iloc[-1]['date'].date()}\n")

    # ── 跑每個視窗的 OOS 測試 ─────────────────────────────────────
    oos_results = []
    for w in windows:
        console.print(
            f"[dim]視窗 {w['window']}/{len(windows)}  "
            f"訓練 {w['train_start']}~{w['train_end']}  "
            f"OOS {w['test_start']}~{w['test_end']}[/dim]"
        )
        try:
            m = run_backtest(
                strategy_cls,
                w["test_df"],       # 只用 OOS 資料跑
                stock_id=stock_id,
                plot=plot,
                strategy_params=strategy_params,
            )
            m["window"]     = w["window"]
            m["test_start"] = w["test_start"]
            m["test_end"]   = w["test_end"]
            oos_results.append(m)
        except Exception as e:
            console.print(f"[red]  視窗 {w['window']} 失敗: {e}[/red]")

    if not oos_results:
        return {}

    summary = _summarize(oos_results)
    _print_results(oos_results, summary)
    return summary


def _summarize(results: list) -> dict:
    rets   = [r["total_return_pct"] for r in results]
    sharpes = [r["sharpe_ratio"] for r in results if r.get("sharpe_ratio")]
    wins   = [r["win_rate_pct"]     for r in results]
    dds    = [r["max_drawdown_pct"] for r in results]

    pos_windows = sum(1 for r in rets if r > 0)
    n = len(results)

    is_robust = (pos_windows / n >= 0.6) and (float(np.mean(rets)) > 0)

    return {
        "windows":           n,
        "positive_windows":  pos_windows,
        "consistency_pct":   round(pos_windows / n * 100, 1),
        "avg_oos_return":    round(float(np.mean(rets)),   2),
        "std_oos_return":    round(float(np.std(rets)),    2),
        "avg_sharpe":        round(float(np.mean(sharpes)),3) if sharpes else None,
        "avg_win_rate":      round(float(np.mean(wins)),   1),
        "avg_max_dd":        round(float(np.mean(dds)),    2),
        "is_robust":         is_robust,
    }


def _print_results(results: list, summary: dict):
    # 各視窗明細
    table = Table(
        title="Walk-Forward OOS 逐視窗績效",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("視窗",    justify="center", width=5)
    table.add_column("OOS 期間",             width=24)
    table.add_column("報酬率%", justify="right", width=9)
    table.add_column("夏普",    justify="right", width=8)
    table.add_column("最大回撤%", justify="right", width=10)
    table.add_column("勝率%",   justify="right", width=7)
    table.add_column("交易數",  justify="right", width=7)

    for r in results:
        col = "green" if r["total_return_pct"] > 0 else "red"
        sharpe = f"{r['sharpe_ratio']:.3f}" if r.get("sharpe_ratio") else "N/A"
        table.add_row(
            str(r["window"]),
            f"{r['test_start']} ~ {r['test_end']}",
            f"[{col}]{r['total_return_pct']:+.2f}[/{col}]",
            sharpe,
            f"{r['max_drawdown_pct']:.2f}",
            f"{r['win_rate_pct']:.1f}",
            str(int(r["total_trades"])),
        )

    console.print(table)

    # 判定
    verdict = (
        "[bold green]✓ 策略穩健 — 可考慮進入紙盤[/bold green]"
        if summary["is_robust"] else
        "[bold red]✗ 策略可能過擬合 — 慎用[/bold red]"
    )

    console.print(f"""
[bold]Walk-Forward 彙總[/bold]
  正報酬視窗：[cyan]{summary['positive_windows']}/{summary['windows']}[/cyan] ({summary['consistency_pct']:.0f}%)
  平均 OOS 報酬：[cyan]{summary['avg_oos_return']:+.2f}%[/cyan]
  報酬標準差：  {summary['std_oos_return']:.2f}%
  平均夏普比率：{summary['avg_sharpe'] if summary['avg_sharpe'] else 'N/A'}
  平均最大回撤：{summary['avg_max_dd']:.2f}%
  平均勝率：    {summary['avg_win_rate']:.1f}%

  判定：{verdict}
  （標準：OOS 正報酬 ≥ 60% 且 平均報酬 > 0）
""")
