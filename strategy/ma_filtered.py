"""
均線交叉策略 v2 — 趨勢過濾 + 量能確認
解決 Walk-Forward 發現的過擬合問題

Walk-Forward 診斷：
  原策略 OOS 正報酬只有 36%，代表策略只在特定市場狀態有效
  根因：在空頭環境也做多，且沒有量能確認，假訊號多

改進項目：
  1. 趨勢過濾：收盤 > MA60（長期多頭結構）才考慮進場
  2. 量能確認：進場日成交量 > 5日均量 × 1.5 倍
  3. 出場改善：持倉至死亡交叉 or 跌破 MA60，不強制隔日出場
"""
import backtrader as bt
from .base import BaseStrategy


class MAFilteredCross(BaseStrategy):
    params = (
        ("fast_period",    5),
        ("slow_period",   20),
        ("trend_period",  60),   # 長期趨勢均線
        ("vol_mult",     1.5),   # 成交量需 > 5日均量 × N 倍
        ("trade_size", 1000),
    )

    def __init__(self):
        self.fast_ma   = bt.indicators.SMA(self.data.close,  period=self.p.fast_period)
        self.slow_ma   = bt.indicators.SMA(self.data.close,  period=self.p.slow_period)
        self.trend_ma  = bt.indicators.SMA(self.data.close,  period=self.p.trend_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.vol_sma   = bt.indicators.SMA(self.data.volume, period=5)
        self.entry_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        in_position = self.position.size > 0
        close    = self.data.close[0]
        vol      = self.data.volume[0]
        vol_avg  = self.vol_sma[0]
        trend    = self.trend_ma[0]

        # ── 出場 ──────────────────────────────────────────────────
        if in_position and self.entry_price:
            # 停損 -2%
            if self.stop_loss_check(self.entry_price, close):
                self.log(f"停損 @ {close:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return
            # 死亡交叉
            if self.crossover < 0:
                self.log(f"死亡交叉出場 @ {close:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return
            # 跌破趨勢線（環境轉空）
            if close < trend:
                self.log(f"跌破趨勢線 @ {close:.2f}  MA{self.p.trend_period}:{trend:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return

        # ── 進場 ──────────────────────────────────────────────────
        if not in_position:
            golden_cross = self.crossover > 0
            above_trend  = close > trend            # 多頭環境
            volume_ok    = vol > vol_avg * self.p.vol_mult  # 量能放大

            if golden_cross and above_trend and volume_ok:
                ratio = vol / vol_avg if vol_avg else 0
                self.log(
                    f"[v2] 黃金交叉買入 @ {close:.2f}  "
                    f"MA{self.p.trend_period}:{trend:.2f}  量比:{ratio:.2f}"
                )
                self.order = self.buy(size=self.p.trade_size)
                self.entry_price = close

    def notify_order(self, order):
        super().notify_order(order)
        if order.status == order.Completed:
            self.order = None
