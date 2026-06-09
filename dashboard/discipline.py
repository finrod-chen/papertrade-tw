"""
紀律計分卡（Discipline Scorecard）
=====================================
系統定位轉向後的核心模組。

哲學：賺賠是市場給的（運氣+beta），但「守不守紀律」100% 是你能控制的。
這張表不獎勵賺錢，只獎勵紀律。長期守紀律的人，才有資格談賺錢。

評分維度（每項 0~100，總分加權平均）：
  1. 停損紀律   — 虧損單是否在 -2% 內就砍（沒讓虧損擴大）
  2. 當沖紀律   — 是否當日平倉（沒凹單留倉）
  3. 不亂凹    — MANUAL 出場比例（破壞系統的次數）
  4. 不過度交易 — 每個交易日的進場次數
  5. 不報復交易 — 虧損後是否冷靜（沒有立刻追單）
"""
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from paper_trade.journal import load_journal
from config import MAX_LOSS_PER_TRADE

console = Console()


def _parse(ts: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.now()


def compute_scorecard() -> dict:
    records = load_journal()
    if not records:
        return {}

    n = len(records)
    losers = [r for r in records if r.net_pnl < 0]

    # ── 1. 停損紀律：虧損單是否守住 -2% ──────────────────────
    # 計算每筆虧損的實際虧損% vs 規則上限
    breaches = 0
    for r in losers:
        loss_pct = (r.exit_price - r.entry_price) / r.entry_price
        # 多單虧損為負；超過 -MAX_LOSS 視為破戒（加 1% 緩衝給滑價）
        if loss_pct < -(MAX_LOSS_PER_TRADE + 0.01):
            breaches += 1
    stop_score = 100 if not losers else max(0, (1 - breaches / len(losers)) * 100)

    # ── 2. 當沖紀律：當日平倉比例 ────────────────────────────
    same_day = sum(
        1 for r in records
        if _parse(r.entry_time).date() == _parse(r.exit_time).date()
    )
    daytrade_score = same_day / n * 100

    # ── 3. 不亂凹：非 MANUAL 出場比例 ────────────────────────
    manual = sum(1 for r in records if r.exit_reason == "MANUAL")
    discipline_score = (1 - manual / n) * 100

    # ── 4. 不過度交易：每個交易日 ≤ 3 筆為佳 ────────────────
    by_day = {}
    for r in records:
        d = _parse(r.entry_time).date()
        by_day[d] = by_day.get(d, 0) + 1
    active_days = len(by_day)
    avg_per_day = n / active_days if active_days else 0
    # 每日 ≤3 筆 = 100，每多 1 筆扣 20
    overtrade_score = max(0, 100 - max(0, avg_per_day - 3) * 20)

    # ── 5. 不報復交易：虧損後 30 分鐘內又進場 = 報復 ─────────
    sorted_rec = sorted(records, key=lambda r: _parse(r.entry_time))
    revenge = 0
    for i in range(1, len(sorted_rec)):
        prev = sorted_rec[i - 1]
        curr = sorted_rec[i]
        if prev.net_pnl < 0:
            gap = (_parse(curr.entry_time) - _parse(prev.exit_time)).total_seconds() / 60
            if 0 <= gap <= 30:
                revenge += 1
    revenge_score = max(0, (1 - revenge / n) * 100)

    # ── 加權總分 ─────────────────────────────────────────────
    weights = {
        "停損紀律":   (stop_score,       0.30),
        "當沖紀律":   (daytrade_score,   0.20),
        "不亂凹系統": (discipline_score, 0.20),
        "不過度交易": (overtrade_score,  0.15),
        "不報復交易": (revenge_score,    0.15),
    }
    total = sum(s * w for s, w in weights.values())

    return {
        "total_trades":   n,
        "active_days":     active_days,
        "avg_per_day":     round(avg_per_day, 1),
        "stop_breaches":   breaches,
        "manual_exits":    manual,
        "revenge_trades":  revenge,
        "scores":          {k: round(v[0], 1) for k, v in weights.items()},
        "weights":         {k: v[1] for k, v in weights.items()},
        "total_score":     round(total, 1),
    }


def _grade(score: float) -> tuple[str, str]:
    if score >= 90:  return "A+", "green"
    if score >= 80:  return "A",  "green"
    if score >= 70:  return "B",  "cyan"
    if score >= 60:  return "C",  "yellow"
    return "D", "red"


def show_scorecard():
    sc = compute_scorecard()
    if not sc:
        console.print("[yellow]尚無交易紀錄，先用 `py main.py paper` 累積幾筆[/yellow]")
        return

    table = Table(title="紀律計分卡", header_style="bold cyan", show_lines=True)
    table.add_column("紀律維度", width=14)
    table.add_column("得分", justify="right", width=8)
    table.add_column("權重", justify="right", width=7)
    table.add_column("評語", width=28)

    notes = {
        "停損紀律":   f"破戒 {sc['stop_breaches']} 次（虧損超過 -{int(MAX_LOSS_PER_TRADE*100)}%）",
        "當沖紀律":   f"當日平倉率",
        "不亂凹系統": f"手動干預 {sc['manual_exits']} 次",
        "不過度交易": f"平均 {sc['avg_per_day']} 筆/日",
        "不報復交易": f"虧損後追單 {sc['revenge_trades']} 次",
    }

    for dim, score in sc["scores"].items():
        g, color = _grade(score)
        table.add_row(
            dim,
            f"[{color}]{score:.0f} {g}[/{color}]",
            f"{sc['weights'][dim]*100:.0f}%",
            notes.get(dim, ""),
        )

    console.print(table)

    g, color = _grade(sc["total_score"])
    console.print(Panel(
        f"[bold {color}]紀律總分：{sc['total_score']:.0f} / 100   等級 {g}[/bold {color}]\n"
        f"[dim]共 {sc['total_trades']} 筆交易，{sc['active_days']} 個交易日[/dim]\n\n"
        + _advice(sc),
        title="總評", border_style=color,
    ))


def _advice(sc: dict) -> str:
    tips = []
    s = sc["scores"]
    if s["停損紀律"] < 80:
        tips.append("• [red]停損是紅線[/red]：虧損單一定要在 -2% 砍掉，凹單是爆倉之母")
    if s["當沖紀律"] < 80:
        tips.append("• [yellow]凹單留倉[/yellow]：當沖就該當日結清，留倉等於改變遊戲規則")
    if s["不亂凹系統"] < 80:
        tips.append("• [yellow]太常手動干預[/yellow]：既然定了策略就執行，事後諸葛不算數")
    if s["不過度交易"] < 80:
        tips.append("• [yellow]交易過量[/yellow]：手續費吃掉利潤，少即是多")
    if s["不報復交易"] < 80:
        tips.append("• [red]報復性交易[/red]：虧損後立刻追單是情緒，先離開螢幕 30 分鐘")
    if not tips:
        tips.append("• [green]紀律優異！[/green]繼續保持，這比賺錢更難得")
    return "\n".join(tips)
