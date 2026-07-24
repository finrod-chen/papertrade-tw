"""
誠實的樣本外驗證（Out-of-Sample Validation）
=================================================
目的：戳破「樣本內過度優化」的假象

做法：
  1. 訓練期(IS) 2020-2022：對每股做網格搜索，挑最佳參數
  2. 測試期(OOS) 2023-2024：用上面挑的參數，跑從沒看過的資料
  3. 對比基準：同期間 buy-and-hold 0050

判讀：
  - 若 OOS 報酬 ≈ IS 報酬 → 策略真有效
  - 若 OOS 報酬 << IS 報酬 → 樣本內過擬合，IS 的好看是假象
  - 若 OOS < 大盤 buy-and-hold → 策略沒有超額價值
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from rich.console import Console
from rich.table import Table
from data.fetcher import fetch_daily_ohlcv
from backtest.optimizer import grid_search
from backtest.runner import run_backtest
from strategy.ma_filtered import MAFilteredCross
from scripts.daily_scan import load_watchlist

console = Console()

IS_START,  IS_END  = "2020-01-01", "2022-12-31"   # 訓練期
OOS_START, OOS_END = "2023-01-01", "2024-12-31"   # 測試期（從沒看過）

PARAM_GRID = {
    "fast_period":  [5, 8, 10],
    "slow_period":  [15, 20, 30],
    "trend_period": [40, 60],
    "vol_mult":     [1.2, 1.5],
}


def buy_and_hold(df: pd.DataFrame) -> float:
    """買進並持有報酬率%"""
    first = df.iloc[0]["close"]
    last  = df.iloc[-1]["close"]
    return (last - first) / first * 100


def validate():
    watchlist = load_watchlist()
    console.print(f"\n[bold cyan]樣本外驗證[/bold cyan]")
    console.print(f"  訓練期(找參數): {IS_START} ~ {IS_END}")
    console.print(f"  測試期(驗收)  : {OOS_START} ~ {OOS_END}  [dim]← 從沒看過[/dim]\n")

    rows = []
    for stock in watchlist:
        sid, name = stock["id"], stock["name"]
        try:
            df_is  = fetch_daily_ohlcv(sid, IS_START,  IS_END,  use_cache=True)
            df_oos = fetch_daily_ohlcv(sid, OOS_START, OOS_END, use_cache=True)
            if len(df_is) < 80 or len(df_oos) < 60:
                continue

            # 1. 訓練期找最佳參數（靜默；min_trades 過濾避免挑到 1~2 筆賭中的雜訊參數）
            res = grid_search(MAFilteredCross, df_is, PARAM_GRID,
                              stock_id=sid, metric="total_return_pct", top_n=1,
                              min_trades=5, verbose=False)
            if res.empty:
                continue
            best = res.iloc[0]
            params = {k: (float(best[k]) if k == "vol_mult" else int(best[k]))
                      for k in PARAM_GRID}
            is_ret = float(best["total_return_pct"])

            # 2. 測試期用該參數驗收
            m = run_backtest(MAFilteredCross, df_oos, stock_id=sid,
                             plot=False, strategy_params=params, verbose=False)
            oos_ret = m["total_return_pct"]

            # 3. 基準：同期 buy-and-hold
            bh = buy_and_hold(df_oos)

            rows.append({
                "sid": sid, "name": name,
                "is_ret": is_ret, "oos_ret": oos_ret, "bh": bh,
                "oos_trades": m["total_trades"],
                "beat_bh": oos_ret > bh,
            })
        except Exception as e:
            console.print(f"[dim red]{sid} 失敗: {e}[/dim red]")

    _report(rows)


def _report(rows: list):
    if not rows:
        console.print("[red]無結果[/red]")
        return

    table = Table(title="樣本內 vs 樣本外 對照", header_style="bold cyan", show_lines=True)
    table.add_column("代號", style="cyan", width=6)
    table.add_column("名稱", width=8)
    table.add_column("IS報酬%", justify="right", width=9)
    table.add_column("OOS報酬%", justify="right", width=10)
    table.add_column("買進持有%", justify="right", width=11)
    table.add_column("贏大盤?", justify="center", width=8)
    table.add_column("OOS交易", justify="right", width=8)

    for r in rows:
        oc = "green" if r["oos_ret"] > 0 else "red"
        beat = "[green]✓[/green]" if r["beat_bh"] else "[red]✗[/red]"
        table.add_row(
            r["sid"], r["name"],
            f"{r['is_ret']:+.1f}",
            f"[{oc}]{r['oos_ret']:+.1f}[/{oc}]",
            f"{r['bh']:+.1f}",
            beat,
            str(r["oos_trades"]),
        )
    console.print(table)

    import numpy as np
    is_avg   = np.mean([r["is_ret"]  for r in rows])
    oos_avg  = np.mean([r["oos_ret"] for r in rows])
    bh_avg   = np.mean([r["bh"]      for r in rows])
    beat_cnt = sum(1 for r in rows if r["beat_bh"])
    oos_pos  = sum(1 for r in rows if r["oos_ret"] > 0)
    n        = len(rows)

    decay = (1 - oos_avg / is_avg) * 100 if is_avg else 0

    console.print(f"""
[bold]═══ 誠實的結論 ═══[/bold]
  樣本內平均報酬(IS) : [yellow]{is_avg:+.2f}%[/yellow]   ← 優化出來的好看數字
  樣本外平均報酬(OOS): [{'green' if oos_avg>0 else 'red'}]{oos_avg:+.2f}%[/{'green' if oos_avg>0 else 'red'}]   ← 真實的預測力
  績效衰減           : [red]{decay:.0f}%[/red]  (IS→OOS 掉了多少)

  買進持有平均(基準) : {bh_avg:+.2f}%
  OOS 贏過大盤       : [cyan]{beat_cnt}/{n}[/cyan] ({beat_cnt/n*100:.0f}%)
  OOS 正報酬         : [cyan]{oos_pos}/{n}[/cyan] ({oos_pos/n*100:.0f}%)

  [dim]判讀：衰減 >50% = 嚴重過擬合；贏大盤 <50% = 策略無超額價值[/dim]
""")


if __name__ == "__main__":
    validate()
