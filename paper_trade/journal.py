"""交易日誌 — 每筆進出場紀錄 CSV"""
import csv
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from config import LOG_DIR

JOURNAL_PATH = os.path.join(LOG_DIR, "trade_journal.csv")

_FIELDS = [
    "trade_id", "stock_id", "side", "entry_time", "entry_price",
    "exit_time", "exit_price", "size", "gross_pnl", "commission",
    "net_pnl", "exit_reason", "note",
]


@dataclass
class TradeRecord:
    trade_id: str
    stock_id: str
    side: str           # "BUY" | "SELL_SHORT"
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    size: int
    gross_pnl: float
    commission: float
    net_pnl: float
    exit_reason: str    # "SIGNAL" | "STOP_LOSS" | "EOD" | "MANUAL"
    note: str = ""


def _ensure_header():
    if not os.path.exists(JOURNAL_PATH):
        with open(JOURNAL_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDS)
            writer.writeheader()


def append_trade(record: TradeRecord):
    _ensure_header()
    with open(JOURNAL_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writerow(asdict(record))


def load_journal() -> list[TradeRecord]:
    if not os.path.exists(JOURNAL_PATH):
        return []
    records = []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(TradeRecord(
                trade_id=row["trade_id"],
                stock_id=row["stock_id"],
                side=row["side"],
                entry_time=row["entry_time"],
                entry_price=float(row["entry_price"]),
                exit_time=row["exit_time"],
                exit_price=float(row["exit_price"]),
                size=int(row["size"]),
                gross_pnl=float(row["gross_pnl"]),
                commission=float(row["commission"]),
                net_pnl=float(row["net_pnl"]),
                exit_reason=row["exit_reason"],
                note=row.get("note", ""),
            ))
    return records
