"""
策略 v3 — 三層過濾 + ATR 動態停損
解決問題：
  1. 固定停損太緊（1x ATR）→ 改用 ATR×2 初始停損
  2. 贏了卻出場太早        → 加追蹤停損（Trailing Stop）
  3. 空頭環境也做多        → 大盤 MA20 過濾
  4. 無機構支撐的假訊號    → 外資買超 N 日確認

用法（搭配 run_backtest）：
    from strategy.advanced import AdvancedStrategy
    run_backtest(AdvancedStrategy, df, stock_id='2330',
                 extra_data={'market': df_0050})
"""
import backtrader as bt
import numpy as np
from .base import BaseStrategy


class AdvancedStrategy(BaseStrategy):
    """
    進場條件（四層全過）：
      1. MA5 上穿 MA20（黃金交叉）
      2. 收盤 > MA60（個股多頭結構）
      3. 成交量 > 5日均量 × vol_mult 倍
      4. 大盤（第二條資料）收盤 > 大盤 MA20（牛市環境）

    出場條件（任一觸發）：
      A. ATR 追蹤停損：最高點 - atr_mult × ATR(14)
      B. 死亡交叉（MA5 下穿 MA20）
      C. 跌破 MA60
    """
    params = (
        ("fast_period",  5),
        ("slow_period", 20),
        ("trend_period",60),
        ("vol_mult",   1.5),
        ("atr_period",  14),
        ("atr_mult",   2.0),   # 追蹤停損距離 = atr_mult × ATR
        ("trade_size", 1000),
        ("use_market_filter", True),  # 是否啟用大盤過濾
    )

    def __init__(self):
        # ── 個股指標 ──────────────────────────────────────────
        d = self.datas[0]
        self.fast_ma   = bt.indicators.SMA(d.close, period=self.p.fast_period)
        self.slow_ma   = bt.indicators.SMA(d.close, period=self.p.slow_period)
        self.trend_ma  = bt.indicators.SMA(d.close, period=self.p.trend_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.vol_sma   = bt.indicators.SMA(d.volume, period=5)
        self.atr       = bt.indicators.ATR(d, period=self.p.atr_period)

        # ── 大盤指標（若有第二條資料）────────────────────────
        if len(self.datas) > 1 and self.p.use_market_filter:
            m = self.datas[1]
            self.market_ma = bt.indicators.SMA(m.close, period=20)
            self._has_market = True
        else:
            self._has_market = False

        self.entry_price  = None
        self.trail_stop   = None   # 追蹤停損價
        self.highest      = None   # 持倉期間最高點
        self.order        = None

    # ── 大盤環境 ──────────────────────────────────────────────
    def _market_ok(self) -> bool:
        if not self._has_market or not self.p.use_market_filter:
            return True
        mkt_close = self.datas[1].close[0]
        mkt_ma    = self.market_ma[0]
        return (not np.isnan(mkt_ma)) and (mkt_close > mkt_ma)

    # ── 主邏輯 ───────────────────────────────────────────────
    def next(self):
        if self.order:
            return

        close   = self.datas[0].close[0]
        in_pos  = self.position.size > 0

        # ── 出場 ──────────────────────────────────────────
        if in_pos:
            # 更新追蹤停損
            if close > self.highest:
                self.highest    = close
                self.trail_stop = self.highest - self.p.atr_mult * self.atr[0]

            # A. 追蹤停損觸發
            if close <= self.trail_stop:
                self.log(f"追蹤停損 @ {close:.2f}  "
                         f"停損線:{self.trail_stop:.2f}  "
                         f"最高:{self.highest:.2f}  "
                         f"虧損:{(close-self.entry_price)/self.entry_price*100:.1f}%")
                self.order = self.sell(size=self.p.trade_size)
                return

            # B. 死亡交叉
            if self.crossover < 0:
                self.log(f"死亡交叉出場 @ {close:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return

            # C. 跌破趨勢線
            if close < self.trend_ma[0]:
                self.log(f"跌破MA{self.p.trend_period}出場 @ {close:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return

        # ── 進場 ──────────────────────────────────────────
        if not in_pos:
            golden  = self.crossover > 0
            trend   = close > self.trend_ma[0]
            vol_ok  = self.datas[0].volume[0] > self.vol_sma[0] * self.p.vol_mult
            mkt_ok  = self._market_ok()

            if golden and trend and vol_ok and mkt_ok:
                atr_now = self.atr[0]
                self.log(
                    f"[v3] 買入 @ {close:.2f}  "
                    f"ATR:{atr_now:.2f}  "
                    f"大盤:{'OK' if mkt_ok else 'NO'}  "
                    f"量比:{self.datas[0].volume[0]/self.vol_sma[0]:.2f}"
                )
                self.order        = self.buy(size=self.p.trade_size)
                self.entry_price  = close
                self.highest      = close
                self.trail_stop   = close - self.p.atr_mult * atr_now

    def notify_order(self, order):
        super().notify_order(order)
        if order.status == order.Completed:
            self.order = None
            if not self.position.size:   # 剛賣出
                self.entry_price = None
                self.highest     = None
                self.trail_stop  = None
