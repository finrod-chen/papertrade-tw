"""部位管理"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    stock_id: str
    entry_price: float             # 含滑價的實際成交價
    size: int                      # 股數（正數=多，負數=空）
    entry_time: datetime = field(default_factory=datetime.now)
    stop_loss_price: Optional[float] = None
    entry_commission: float = 0.0  # 進場手續費（平倉時計入淨損益）

    @property
    def is_long(self) -> bool:
        return self.size > 0

    @property
    def market_value(self) -> float:
        return self.entry_price * abs(self.size)

    def unrealized_pnl(self, current_price: float) -> float:
        if self.is_long:
            return (current_price - self.entry_price) * self.size
        return (self.entry_price - current_price) * abs(self.size)

    def unrealized_pnl_pct(self, current_price: float) -> float:
        return self.unrealized_pnl(current_price) / self.market_value * 100


class PositionManager:
    def __init__(self, max_loss_pct: float = 0.02):
        self.positions: dict[str, Position] = {}
        self.max_loss_pct = max_loss_pct

    def open(self, stock_id: str, price: float, size: int,
             entry_commission: float = 0.0) -> Position:
        if stock_id in self.positions:
            raise ValueError(f"{stock_id} 已有部位，請先平倉")
        stop = price * (1 - self.max_loss_pct) if size > 0 else price * (1 + self.max_loss_pct)
        pos = Position(stock_id=stock_id, entry_price=price, size=size,
                       stop_loss_price=stop, entry_commission=entry_commission)
        self.positions[stock_id] = pos
        return pos

    def close(self, stock_id: str) -> Optional[Position]:
        return self.positions.pop(stock_id, None)

    def should_stop_loss(self, stock_id: str, current_price: float) -> bool:
        pos = self.positions.get(stock_id)
        if not pos or not pos.stop_loss_price:
            return False
        if pos.is_long:
            return current_price <= pos.stop_loss_price
        return current_price >= pos.stop_loss_price

    def get(self, stock_id: str) -> Optional[Position]:
        return self.positions.get(stock_id)

    def all_positions(self) -> list[Position]:
        return list(self.positions.values())
