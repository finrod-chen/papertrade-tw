"""
每支股票個別參數優化
- 對 watchlist 所有股票跑小型網格搜索
- 最佳參數存到 data/optimal_params.json
- 之後 portfolio_run.py 自動讀取
用法：py scripts/per_stock_optimize.py [--force]
"""
import sys, os, json, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from data.fetcher import fetch_daily_ohlcv
from backtest.optimizer import grid_search
from strategy.ma_filtered import MAFilteredCross
from scripts.daily_scan import load_watchlist
from rich.console import Console

console = Console()

PARAMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "optimal_params.json"
)

# 小型搜索網格（速度快，避免過擬合）
PARAM_GRID = {
    "fast_period":  [5, 8, 10],
    "slow_period":  [15, 20, 30],
    "trend_period": [40, 60],
    "vol_mult":     [1.2, 1.5],
}


def load_optimal() -> dict:
    if os.path.exists(PARAMS_PATH):
        with open(PARAMS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_optimal(data: dict):
    os.makedirs(os.path.dirname(PARAMS_PATH), exist_ok=True)
    with open(PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def optimize_all(start: str = "2020-01-01", end: str = "2024-01-01",
                 force: bool = False, min_trades: int = 3) -> dict:
    watchlist = load_watchlist()
    optimal   = load_optimal()

    console.print(
        f"\n[bold cyan]每股參數優化[/bold cyan]  "
        f"{len(watchlist)} 支  {start}~{end}\n"
        f"搜索空間：{sum(len(v) for v in PARAM_GRID.values())} 個參數 × "
        f"{__import__('math').prod(len(v) for v in PARAM_GRID.values())} 組合\n"
    )

    for stock in watchlist:
        sid  = stock["id"]
        name = stock["name"]

        if not force and sid in optimal:
            console.print(f"[dim]{sid} {name} 已有參數，跳過[/dim]")
            continue

        try:
            df = fetch_daily_ohlcv(sid, start, end, use_cache=True)
            if len(df) < 80:
                console.print(f"[dim]{sid} 資料不足，跳過[/dim]")
                continue

            console.print(f"\n[cyan]{sid}[/cyan] {name}  搜索中...")
            results = grid_search(
                MAFilteredCross, df,
                param_grid=PARAM_GRID,
                stock_id=sid,
                metric="total_return_pct",
                top_n=3,
                min_trades=min_trades,
                verbose=False,
            )

            if results.empty:
                continue

            best = results.iloc[0]
            best_params = {
                k: (float(best[k]) if k == "vol_mult" else int(best[k]))
                for k in PARAM_GRID
            }
            optimal[sid] = {
                "name":      name,
                "params":    best_params,
                "return":    round(float(best["total_return_pct"]), 2),
                "sharpe":    round(float(best["sharpe_ratio"]), 3) if best.get("sharpe_ratio") else None,
                "win_rate":  round(float(best["win_rate_pct"]), 1),
                "trades":    int(best["total_trades"]),
                "updated":   datetime.now().strftime("%Y-%m-%d"),
            }
            save_optimal(optimal)
            console.print(
                f"  [green]最佳[/green] {best_params}  "
                f"報酬:{best['total_return_pct']:+.2f}%  "
                f"勝率:{best['win_rate_pct']:.1f}%  "
                f"交易:{int(best['total_trades'])}次"
            )

        except Exception as e:
            console.print(f"[red]  {sid} 失敗: {e}[/red]")

    console.print(f"\n[bold]完成！{len(optimal)} 支股票最佳參數已存至 {PARAMS_PATH}[/bold]")
    return optimal


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",  default="2020-01-01")
    parser.add_argument("--end",    default="2024-01-01")
    parser.add_argument("--force",  action="store_true", help="重新搜索已有結果的股票")
    parser.add_argument("--min-trades", type=int, default=3, dest="min_trades")
    args = parser.parse_args()
    optimize_all(args.start, args.end, args.force, args.min_trades)
