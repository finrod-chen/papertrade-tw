"""
使用者設定持久化
存 data/settings.json，目前管理：初始資金
"""
import os
import json
from config import INITIAL_CAPITAL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, "data", "settings.json")

DEFAULTS = {"initial_capital": INITIAL_CAPITAL}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return {**DEFAULTS, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(patch: dict) -> dict:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    cur = load_settings()
    cur.update(patch)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return cur


def get_initial_capital() -> float:
    return float(load_settings()["initial_capital"])
