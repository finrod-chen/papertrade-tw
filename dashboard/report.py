"""績效報表 — 月度/累計統計"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from paper_trade.journal import load_journal, TradeRecord
from config import INITIAL_CAPITAL, LOG_DIR

plt.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]


def build_report(save_dir: str = LOG_DIR):
    records = load_journal()
    if not records:
        print("尚無交易紀錄")
        return

    df = pd.DataFrame([
        {
            "exit_time": pd.to_datetime(r.exit_time),
            "stock_id": r.stock_id,
            "net_pnl": r.net_pnl,
            "exit_reason": r.exit_reason,
        }
        for r in records
    ])
    df = df.sort_values("exit_time").reset_index(drop=True)
    df["cumulative_pnl"] = df["net_pnl"].cumsum()
    df["equity"] = INITIAL_CAPITAL + df["cumulative_pnl"]

    # 月度分組
    df["month"] = df["exit_time"].dt.to_period("M")
    monthly = df.groupby("month").agg(
        trades=("net_pnl", "count"),
        pnl=("net_pnl", "sum"),
        win_rate=("net_pnl", lambda x: (x > 0).mean() * 100),
    ).reset_index()

    _print_monthly(monthly)
    _plot_equity(df, save_dir)


def _print_monthly(monthly: pd.DataFrame):
    print(f"\n{'='*60}")
    print(f"{'月份':<10}{'交易筆數':>8}{'淨損益':>12}{'勝率':>8}")
    print(f"{'─'*60}")
    for _, row in monthly.iterrows():
        sign = "+" if row["pnl"] >= 0 else ""
        print(f"{str(row['month']):<10}{row['trades']:>8.0f}{sign}{row['pnl']:>11,.0f}{row['win_rate']:>7.1f}%")
    print(f"{'='*60}\n")


def _plot_equity(df: pd.DataFrame, save_dir: str):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

    # 權益曲線
    ax1 = axes[0]
    ax1.plot(df["exit_time"], df["equity"], color="#2196F3", linewidth=1.5, label="資金曲線")
    ax1.axhline(INITIAL_CAPITAL, color="gray", linestyle="--", linewidth=0.8, label="初始資金")
    ax1.fill_between(df["exit_time"], INITIAL_CAPITAL, df["equity"],
                     where=df["equity"] >= INITIAL_CAPITAL, alpha=0.15, color="green")
    ax1.fill_between(df["exit_time"], INITIAL_CAPITAL, df["equity"],
                     where=df["equity"] < INITIAL_CAPITAL, alpha=0.15, color="red")
    ax1.set_title("紙盤交易權益曲線", fontsize=14)
    ax1.set_ylabel("資金 (元)")
    ax1.legend()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

    # 每日損益柱狀圖
    ax2 = axes[1]
    colors = ["#EF5350" if p >= 0 else "#4CAF50" for p in df["net_pnl"]]
    ax2.bar(df["exit_time"], df["net_pnl"], color=colors, width=0.6)
    ax2.axhline(0, color="gray", linewidth=0.8)
    ax2.set_ylabel("單筆損益")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

    plt.tight_layout()
    out = os.path.join(save_dir, f"equity_curve_{datetime.now().strftime('%Y%m%d')}.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"圖表已儲存：{out}")
    plt.show()
