"""
紙盤交易引擎
手動模式：命令列互動下單、紀錄損益
"""
import uuid
from datetime import datetime
from rich.console import Console
from rich.table import Table
from .position import PositionManager
from .journal import TradeRecord, append_trade, load_journal
from config import (
    COMMISSION_RATE, TAX_RATE, SLIPPAGE,
    INITIAL_CAPITAL, MAX_DAILY_LOSS,
)

console = Console()


def _calc_commission(price: float, size: int, is_sell: bool) -> float:
    comm = price * size * COMMISSION_RATE
    if is_sell:
        comm += price * size * TAX_RATE
    return round(comm, 2)


class PaperEngine:
    def __init__(self, capital: float = INITIAL_CAPITAL):
        self.capital = capital
        self.start_capital = capital
        self.daily_start_capital = capital
        self.pm = PositionManager()
        self._trade_counter = 0

    # ── 下單 ──────────────────────────────────────────────────────────

    def buy(self, stock_id: str, price: float, size: int, note: str = "") -> bool:
        """買進（多單進場）"""
        if not self._check_daily_loss():
            return False

        cost = price * size * (1 + SLIPPAGE)
        commission = _calc_commission(price, size, is_sell=False)
        total_cost = cost + commission

        if total_cost > self.capital:
            console.print(f"[red]資金不足！需要 {total_cost:,.0f}，現有 {self.capital:,.0f}[/red]")
            return False

        self.capital -= total_cost
        pos = self.pm.open(stock_id, price, size)
        self._trade_counter += 1

        console.print(
            f"[green]✓ 買進 {stock_id}  {size}股 @ {price:.2f}  "
            f"手續費:{commission:.0f}  剩餘資金:{self.capital:,.0f}[/green]"
        )
        return True

    def sell(self, stock_id: str, price: float, exit_reason: str = "SIGNAL", note: str = "") -> bool:
        """賣出平倉（多單出場）"""
        pos = self.pm.get(stock_id)
        if not pos:
            console.print(f"[red]無 {stock_id} 部位[/red]")
            return False

        actual_price = price * (1 - SLIPPAGE)
        commission = _calc_commission(price, pos.size, is_sell=True)
        proceeds = actual_price * pos.size - commission
        gross_pnl = (actual_price - pos.entry_price) * pos.size
        net_pnl = gross_pnl - commission

        self.capital += proceeds
        self.pm.close(stock_id)

        record = TradeRecord(
            trade_id=f"T{self._trade_counter:05d}",
            stock_id=stock_id,
            side="BUY",
            entry_time=pos.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            entry_price=pos.entry_price,
            exit_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            exit_price=price,
            size=pos.size,
            gross_pnl=round(gross_pnl, 0),
            commission=round(commission, 0),
            net_pnl=round(net_pnl, 0),
            exit_reason=exit_reason,
            note=note,
        )
        append_trade(record)

        color = "green" if net_pnl >= 0 else "red"
        console.print(
            f"[{color}]✓ 賣出 {stock_id}  {pos.size}股 @ {price:.2f}  "
            f"淨損益:{net_pnl:+,.0f}  ({exit_reason})[/{color}]"
        )
        return True

    # ── 風控 ─────────────────────────────────────────────────────────

    def _check_daily_loss(self) -> bool:
        daily_loss = (self.capital - self.daily_start_capital) / self.daily_start_capital
        if daily_loss <= -MAX_DAILY_LOSS:
            console.print(
                f"[bold red]⚠ 單日虧損達 {daily_loss*100:.1f}%，今日停止交易！[/bold red]"
            )
            return False
        return True

    def check_stop_losses(self, prices: dict[str, float]):
        """傳入 {stock_id: current_price}，自動觸發停損"""
        for stock_id, price in prices.items():
            if self.pm.should_stop_loss(stock_id, price):
                console.print(f"[yellow]⚡ 停損觸發：{stock_id} @ {price:.2f}[/yellow]")
                self.sell(stock_id, price, exit_reason="STOP_LOSS")

    def close_all_eod(self, prices: dict[str, float]):
        """收盤前強制平所有部位"""
        for pos in self.pm.all_positions():
            price = prices.get(pos.stock_id)
            if price:
                self.sell(pos.stock_id, price, exit_reason="EOD")

    # ── 報表 ─────────────────────────────────────────────────────────

    def show_positions(self, prices: dict[str, float] = None):
        table = Table(title="目前部位", show_header=True)
        table.add_column("股票", style="cyan")
        table.add_column("方向")
        table.add_column("股數", justify="right")
        table.add_column("成本", justify="right")
        table.add_column("現價", justify="right")
        table.add_column("未實現損益", justify="right")

        for pos in self.pm.all_positions():
            current = prices.get(pos.stock_id, pos.entry_price) if prices else pos.entry_price
            pnl = pos.unrealized_pnl(current)
            pnl_pct = pos.unrealized_pnl_pct(current)
            color = "green" if pnl >= 0 else "red"
            table.add_row(
                pos.stock_id,
                "多" if pos.is_long else "空",
                f"{pos.size:,}",
                f"{pos.entry_price:.2f}",
                f"{current:.2f}",
                f"[{color}]{pnl:+,.0f} ({pnl_pct:+.1f}%)[/{color}]",
            )

        console.print(table)
        console.print(f"可用資金：[bold]{self.capital:,.0f}[/bold]")

    def show_summary(self):
        records = load_journal()
        if not records:
            console.print("尚無交易紀錄")
            return

        total_pnl = sum(r.net_pnl for r in records)
        wins = [r for r in records if r.net_pnl > 0]
        win_rate = len(wins) / len(records) * 100 if records else 0

        table = Table(title=f"交易總結（共 {len(records)} 筆）")
        table.add_column("指標")
        table.add_column("數值", justify="right")

        table.add_row("總淨損益", f"{total_pnl:+,.0f}")
        table.add_row("勝率", f"{win_rate:.1f}%")
        table.add_row("獲利筆數", str(len(wins)))
        table.add_row("虧損筆數", str(len(records) - len(wins)))
        if wins:
            table.add_row("平均獲利", f"{sum(r.net_pnl for r in wins)/len(wins):,.0f}")
        losers = [r for r in records if r.net_pnl <= 0]
        if losers:
            table.add_row("平均虧損", f"{sum(r.net_pnl for r in losers)/len(losers):,.0f}")

        console.print(table)
