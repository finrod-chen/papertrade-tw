"""
台股紙盤交易系統 — Web App (Flask)
定位：紀律訓練器（非打敗大盤）

啟動：
    py run_web.py
    或  py -m webapp.app
然後瀏覽器開 http://127.0.0.1:5000
"""
import os
import sys
from datetime import datetime, date, timedelta

# 確保能 import 專案根目錄模組
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

# 強制 stdout/stderr 為 UTF-8：引擎用 rich 輸出 ✓⚡⚠ 等字元，
# 避免 Windows cp950 主控台編碼錯誤導致 API 崩潰（部署健壯性）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, jsonify, request, render_template

from config import INITIAL_CAPITAL
from webapp.engine_store import get_engine, save, reset_engine
from webapp.settings_store import load_settings, save_settings

# 股票名稱對照（FinMind 全市場清單，模組層快取）
_STOCK_NAMES = None


def _stock_name(stock_id: str):
    """從 FinMind 全市場清單查股票中文名（兼作代號驗證）"""
    global _STOCK_NAMES
    if _STOCK_NAMES is None:
        try:
            from data.fetcher import fetch_stock_list
            df = fetch_stock_list()
            _STOCK_NAMES = dict(zip(df["stock_id"].astype(str), df["stock_name"]))
        except Exception:
            _STOCK_NAMES = {}
    return _STOCK_NAMES.get(str(stock_id))

app = Flask(__name__, template_folder="templates", static_folder="static")


# ════════════════════════════════════════════════════════════════
#  首頁
# ════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ════════════════════════════════════════════════════════════════
#  帳戶 / 部位
# ════════════════════════════════════════════════════════════════

def _live_prices(stock_ids: list) -> dict:
    if not stock_ids:
        return {}
    try:
        from data.realtime import get_prices
        return get_prices(stock_ids)
    except Exception:
        return {}


@app.route("/api/account")
def api_account():
    engine = get_engine()
    positions = engine.pm.all_positions()
    ids = [p.stock_id for p in positions]
    prices = _live_prices(ids)

    pos_list, position_value = [], 0.0
    for p in positions:
        cur = prices.get(p.stock_id, p.entry_price)
        pnl = p.unrealized_pnl(cur)
        position_value += cur * abs(p.size)
        pos_list.append({
            "stock_id":    p.stock_id,
            "size":        p.size,
            "entry_price": round(p.entry_price, 2),
            "current":     round(cur, 2),
            "stop_loss":   round(p.stop_loss_price, 2) if p.stop_loss_price else None,
            "pnl":         round(pnl, 0),
            "pnl_pct":     round(p.unrealized_pnl_pct(cur), 2),
            "is_live":     p.stock_id in prices,
        })

    equity = engine.capital + position_value
    total_ret = (equity - engine.start_capital) / engine.start_capital * 100

    # 今日已實現損益（從日誌）
    realized_today = 0.0
    try:
        from paper_trade.journal import load_journal
        today = date.today().isoformat()
        for r in load_journal():
            if r.exit_time.startswith(today):
                realized_today += r.net_pnl
    except Exception:
        pass

    return jsonify({
        "cash":           round(engine.capital, 0),
        "position_value": round(position_value, 0),
        "equity":         round(equity, 0),
        "start_capital":  round(engine.start_capital, 0),
        "total_return":   round(total_ret, 2),
        "realized_today": round(realized_today, 0),
        "positions":      pos_list,
    })


@app.route("/api/buy", methods=["POST"])
def api_buy():
    d = request.get_json(force=True)
    engine = get_engine()
    try:
        price, size = float(d["price"]), int(d["size"])
        if price <= 0 or size <= 0:
            return jsonify({"ok": False, "msg": "價格與股數必須為正數"}), 400
        ok = engine.buy(d["stock_id"].strip(), price, size,
                        note=d.get("note", ""))
    except Exception as e:
        return jsonify({"ok": False, "msg": f"參數錯誤：{e}"}), 400
    if ok:
        save(engine)
        return jsonify({"ok": True, "msg": f"已買進 {d['stock_id']}"})
    return jsonify({"ok": False, "msg": "下單失敗（資金不足、已有部位、或觸發單日風控）"}), 400


@app.route("/api/sell", methods=["POST"])
def api_sell():
    d = request.get_json(force=True)
    engine = get_engine()
    reason = d.get("reason", "SIGNAL")
    try:
        price = float(d["price"])
        if price <= 0:
            return jsonify({"ok": False, "msg": "價格必須為正數"}), 400
        ok = engine.sell(d["stock_id"].strip(), price,
                         exit_reason=reason, note=d.get("note", ""))
    except Exception as e:
        return jsonify({"ok": False, "msg": f"參數錯誤：{e}"}), 400
    if ok:
        save(engine)
        return jsonify({"ok": True, "msg": f"已賣出 {d['stock_id']}"})
    return jsonify({"ok": False, "msg": "無此部位"}), 400


@app.route("/api/reset", methods=["POST"])
def api_reset():
    engine = reset_engine()
    return jsonify({"ok": True, "msg": f"帳戶已重置為 {engine.start_capital:,.0f}"})


@app.route("/api/price/<stock_id>")
def api_price(stock_id):
    prices = _live_prices([stock_id])
    p = prices.get(stock_id)
    return jsonify({"stock_id": stock_id, "price": round(p, 2) if p else None})


# ════════════════════════════════════════════════════════════════
#  盤前掃描
# ════════════════════════════════════════════════════════════════

@app.route("/api/watchlist")
def api_watchlist():
    from scripts.daily_scan import load_watchlist
    return jsonify(load_watchlist())


@app.route("/api/watchlist", methods=["POST"])
def api_watchlist_add():
    from scripts.daily_scan import load_watchlist, save_watchlist
    d = request.get_json(force=True)
    sid = str(d.get("id", "")).strip()
    if not sid:
        return jsonify({"ok": False, "msg": "請輸入股票代號"}), 400

    wl = load_watchlist()
    if any(s["id"] == sid for s in wl):
        return jsonify({"ok": False, "msg": f"{sid} 已在清單中"}), 400

    name = str(d.get("name", "")).strip()
    if not name:
        name = _stock_name(sid)
    if not name:
        return jsonify({"ok": False, "msg": f"查無代號 {sid}，請確認或手動填名稱"}), 400

    wl.append({"id": sid, "name": name, "sector": str(d.get("sector", "")).strip() or "自訂"})
    save_watchlist(wl)
    return jsonify({"ok": True, "msg": f"已新增 {sid} {name}"})


@app.route("/api/watchlist/<sid>", methods=["DELETE"])
def api_watchlist_del(sid):
    from scripts.daily_scan import load_watchlist, save_watchlist
    wl = load_watchlist()
    new = [s for s in wl if s["id"] != sid]
    if len(new) == len(wl):
        return jsonify({"ok": False, "msg": "找不到該股票"}), 400
    save_watchlist(new)
    return jsonify({"ok": True, "msg": f"已移除 {sid}"})


# ════════════════════════════════════════════════════════════════
#  設定（初始資金）
# ════════════════════════════════════════════════════════════════

@app.route("/api/settings")
def api_settings_get():
    return jsonify(load_settings())


@app.route("/api/settings", methods=["POST"])
def api_settings_set():
    d = request.get_json(force=True)
    try:
        cap = float(d.get("initial_capital"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "資金格式錯誤"}), 400
    if cap < 10000:
        return jsonify({"ok": False, "msg": "初始資金需至少 10,000"}), 400
    if cap > 1_000_000_000:
        return jsonify({"ok": False, "msg": "初始資金過大"}), 400
    # 變更初始資金等於重新開帳，會重置帳戶
    reset_engine(cap)
    return jsonify({"ok": True, "msg": f"初始資金設為 {cap:,.0f}，帳戶已重置"})


@app.route("/api/scan")
def api_scan():
    from scripts.daily_scan import load_watchlist
    from strategy.signals import consensus_signal
    from data.fetcher import fetch_daily_ohlcv

    lookback = int(request.args.get("lookback", 60))
    today = datetime.today()
    end   = today.strftime("%Y-%m-%d")
    start = (today - timedelta(days=lookback)).strftime("%Y-%m-%d")

    rows = []
    for s in load_watchlist():
        try:
            df = fetch_daily_ohlcv(s["id"], start, end, use_cache=False)
            if len(df) < 25:
                continue
            sig = consensus_signal(df)
            rows.append({
                "id": s["id"], "name": s["name"],
                "sector": s.get("sector", ""),
                **sig,
            })
        except Exception:
            continue

    candidates = [r for r in rows if "BUY" in (r.get("consensus") or "")]
    return jsonify({"date": end, "rows": rows, "candidates": candidates})


# ════════════════════════════════════════════════════════════════
#  交易日誌
# ════════════════════════════════════════════════════════════════

@app.route("/api/journal")
def api_journal():
    from paper_trade.journal import load_journal
    records = load_journal()
    data = [{
        "trade_id":    r.trade_id,
        "stock_id":    r.stock_id,
        "entry_time":  r.entry_time,
        "entry_price": r.entry_price,
        "exit_time":   r.exit_time,
        "exit_price":  r.exit_price,
        "size":        r.size,
        "net_pnl":     r.net_pnl,
        "exit_reason": r.exit_reason,
    } for r in records]
    data.reverse()  # 最新在前
    return jsonify(data)


# ════════════════════════════════════════════════════════════════
#  紀律計分卡 + 大盤對照
# ════════════════════════════════════════════════════════════════

@app.route("/api/discipline")
def api_discipline():
    from dashboard.discipline import compute_scorecard
    sc = compute_scorecard()
    bench = _benchmark_data()
    return jsonify({"scorecard": sc, "benchmark": bench})


def _benchmark_data(benchmark_id: str = "0050") -> dict:
    from paper_trade.journal import load_journal
    records = load_journal()
    if not records:
        return {}

    def _parse(ts):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
        return datetime.now()

    start = min(_parse(r.entry_time) for r in records).strftime("%Y-%m-%d")
    end   = max(_parse(r.exit_time)  for r in records).strftime("%Y-%m-%d")
    paper_pnl = sum(r.net_pnl for r in records)
    from webapp.settings_store import get_initial_capital
    paper_ret = paper_pnl / get_initial_capital() * 100

    bench_ret = None
    try:
        from data.fetcher import fetch_daily_ohlcv
        bdf = fetch_daily_ohlcv(benchmark_id, start, end, use_cache=True)
        if len(bdf) >= 2:
            bench_ret = (bdf.iloc[-1]["close"] - bdf.iloc[0]["close"]) / bdf.iloc[0]["close"] * 100
    except Exception:
        pass

    return {
        "benchmark_id": benchmark_id,
        "start": start, "end": end,
        "paper_return": round(paper_ret, 2),
        "bench_return": round(bench_ret, 2) if bench_ret is not None else None,
        "excess":       round(paper_ret - bench_ret, 2) if bench_ret is not None else None,
        "trade_count":  len(records),
    }


# ════════════════════════════════════════════════════════════════
#  回測
# ════════════════════════════════════════════════════════════════

@app.route("/api/strategies")
def api_strategies():
    from strategy import STRATEGIES
    meta = {
        "ma_cross":    ("均線交叉 (v1)",
                        "最經典的順勢策略。5 日均線向上穿越 20 日均線（黃金交叉）買進，跌破（死亡交叉）賣出。簡單直觀，但盤整時假訊號多、容易被洗。"),
        "rsi":         ("RSI 超買超賣",
                        "逆勢策略。RSI(14) 低於 30 視為超賣買進，高於 70 超買賣出。適合區間震盪行情；單邊趨勢盤會過早進出、錯失大行情。"),
        "bollinger":   ("布林通道反彈",
                        "均值回歸策略。股價跌破下軌後再站回時買進（賭反彈），漲到中軌或上軌時出場。盤整有效；趨勢盤逆勢接刀風險高。"),
        "ma_filtered": ("趨勢過濾 (v2)",
                        "均線交叉的強化版，加兩道濾網：須站上 60 日均線（確認多頭結構）＋ 當日成交量放大。大幅減少假訊號，交易變少但品質提升。"),
        "advanced":    ("ATR 追蹤停損 (v3)",
                        "v2 再加兩項風控：ATR 動態追蹤停損（讓獲利奔跑、虧損快砍）＋ 大盤過濾（只在 0050 站上月線的多頭環境做多）。風控最完整。"),
    }
    return jsonify([
        {"key": k, "label": meta.get(k, (k, ""))[0], "desc": meta.get(k, (k, ""))[1]}
        for k in STRATEGIES
    ])


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    from data.fetcher import fetch_daily_ohlcv
    from backtest.runner import run_backtest
    from strategy import STRATEGIES

    d = request.get_json(force=True)
    cls = STRATEGIES.get(d.get("strategy", "ma_filtered"))
    if not cls:
        return jsonify({"ok": False, "msg": "未知策略"}), 400
    try:
        df = fetch_daily_ohlcv(d["stock"].strip(), d["start"], d["end"])
        if len(df) < 30:
            return jsonify({"ok": False, "msg": "資料不足"}), 400
        m = run_backtest(cls, df, stock_id=d["stock"], plot=False, verbose=False)
        m["bars"] = len(df)
        return jsonify({"ok": True, "metrics": m})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"回測失敗：{e}"}), 400


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"\n  台股紙盤交易系統 Web App")
    print(f"  瀏覽器開啟 → http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
