"""
紙盤引擎狀態持久化
Web 環境跨請求需保留資金/部位，存成 logs/paper_state.json
"""
import os
import json
from datetime import datetime, date
from paper_trade.engine import PaperEngine
from paper_trade.position import Position
from config import INITIAL_CAPITAL, LOG_DIR
from webapp.settings_store import get_initial_capital, save_settings

STATE_PATH = os.path.join(LOG_DIR, "paper_state.json")

_engine = None


def _serialize(engine: PaperEngine) -> dict:
    return {
        "capital":             engine.capital,
        "start_capital":       engine.start_capital,
        "daily_start_capital": engine.daily_start_capital,
        "trade_counter":       engine._trade_counter,
        "date":                date.today().isoformat(),
        "positions": [
            {
                "stock_id":        p.stock_id,
                "entry_price":     p.entry_price,
                "size":            p.size,
                "entry_time":      p.entry_time.isoformat(),
                "stop_loss_price": p.stop_loss_price,
            }
            for p in engine.pm.all_positions()
        ],
    }


def save(engine: PaperEngine):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(_serialize(engine), f, ensure_ascii=False, indent=2)


def _load_into(engine: PaperEngine):
    if not os.path.exists(STATE_PATH):
        return
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine.capital        = data.get("capital", INITIAL_CAPITAL)
    engine.start_capital  = data.get("start_capital", INITIAL_CAPITAL)
    engine._trade_counter = data.get("trade_counter", 0)

    # 跨日：新的一天重置「當日起始資金」用於單日風控
    if data.get("date") == date.today().isoformat():
        engine.daily_start_capital = data.get("daily_start_capital", engine.capital)
    else:
        engine.daily_start_capital = engine.capital

    for pd_ in data.get("positions", []):
        pos = Position(
            stock_id=pd_["stock_id"],
            entry_price=pd_["entry_price"],
            size=pd_["size"],
            entry_time=datetime.fromisoformat(pd_["entry_time"]),
            stop_loss_price=pd_.get("stop_loss_price"),
        )
        engine.pm.positions[pos.stock_id] = pos


def get_engine() -> PaperEngine:
    global _engine
    if _engine is None:
        _engine = PaperEngine(get_initial_capital())
        _load_into(_engine)
    return _engine


def reset_engine(capital: float = None) -> PaperEngine:
    """重置帳戶。傳入 capital 則同時更新初始資金設定。"""
    global _engine
    if capital is not None:
        save_settings({"initial_capital": float(capital)})
    _engine = PaperEngine(get_initial_capital())
    save(_engine)
    return _engine
