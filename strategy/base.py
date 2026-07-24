"""所有策略的基礎類別（Backtrader 用）"""
import backtrader as bt
from config import COMMISSION_RATE, TAX_RATE, SLIPPAGE, MAX_LOSS_PER_TRADE


class TwStockCommission(bt.CommInfoBase):
    """台股手續費 + 證交稅"""
    params = (
        ("commission", COMMISSION_RATE),
        ("tax", TAX_RATE),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
    )

    def _getcommission(self, size, price, pseudoexec):
        # 買進：手續費；賣出：手續費 + 證交稅
        commission = abs(size) * price * self.p.commission
        if size < 0:
            commission += abs(size) * price * self.p.tax
        return commission


class BaseStrategy(bt.Strategy):
    """
    所有策略繼承此類別，內建：
    - 停損邏輯（單筆 -MAX_LOSS_PER_TRADE）
    - 訂單生命週期管理：任何終局狀態（成交/取消/保證金不足/拒絕）
      都會清除 self.order，策略不會因一筆失敗訂單而永久凍結
    - 買單成交時以「實際成交價」回填 entry_price（訊號日收盤價
      與次日開盤成交價有落差，停損基準必須用真實成本）
    """

    def log(self, msg: str, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"[{dt}] {msg}")

    def on_buy_filled(self, price: float):
        """買單成交 hook，子類可覆寫（如重設追蹤停損基準）"""

    def on_position_closed(self):
        """平倉完成 hook，子類可覆寫（如清除追蹤停損狀態）"""

    def notify_order(self, order):
        if order.status in [order.Created, order.Submitted, order.Accepted, order.Partial]:
            return

        if order.status == order.Completed:
            side = "買入" if order.isbuy() else "賣出"
            self.log(
                f"{side} {order.data._name} "
                f"價格:{order.executed.price:.2f} "
                f"數量:{int(order.executed.size)} "
                f"手續費:{order.executed.comm:.0f}"
            )
            if order.isbuy():
                self.entry_price = order.executed.price
                self.on_buy_filled(order.executed.price)
            elif not self.position.size:
                self.entry_price = None
                self.on_position_closed()
        else:
            self.log(f"訂單失敗: {order.Status[order.status]}")

        # 終局狀態一律解鎖，避免 next() 的 `if self.order: return` 永久擋住策略
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(
                f"平倉損益 毛利:{trade.pnl:.0f} 淨利:{trade.pnlcomm:.0f}"
            )

    def stop_loss_check(self, entry_price: float, current_price: float) -> bool:
        """回傳 True 代表觸發停損"""
        loss_pct = (current_price - entry_price) / entry_price
        return loss_pct <= -MAX_LOSS_PER_TRADE
