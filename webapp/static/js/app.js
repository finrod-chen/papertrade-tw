/* 台股紙盤交易系統 — 前端邏輯 */
const App = (() => {

  // ---- 工具 ----
  const $  = (id) => document.getElementById(id);
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("zh-TW"));
  const pct = (n) => (n == null ? "—" : (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%");
  const cls = (n) => (n > 0 ? "up" : n < 0 ? "down" : "");

  async function api(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
  }
  async function post(url, body) {
    return api(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  // ---- 分頁切換 ----
  function initTabs() {
    document.querySelectorAll(".tab").forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        $(btn.dataset.tab).classList.add("active");
        onTab(btn.dataset.tab);
      };
    });
  }
  const TITLES = {
    dashboard: "總覽", scan: "盤前掃描", paper: "紙盤交易",
    discipline: "紀律計分", backtest: "策略回測", settings: "設定",
  };
  function onTab(name) {
    const t = $("pageTitle"); if (t) t.textContent = TITLES[name] || "";
    if (name === "dashboard" || name === "paper") loadAccount();
    if (name === "paper") loadJournal();
    if (name === "discipline") loadDiscipline();
    if (name === "settings") loadSettings();
  }

  // ---- 帳戶 / 部位 ----
  async function loadAccount() {
    const a = await api("/api/account");
    // 頂部 pill
    $("pillEquity").textContent = fmt(a.equity);
    $("pillReturn").textContent = pct(a.total_return);
    $("pillReturn").className = "pill-value " + cls(a.total_return);
    // 總覽統計
    $("dCash").textContent     = fmt(a.cash);
    $("dPosVal").textContent   = fmt(a.position_value);
    $("dEquity").textContent   = fmt(a.equity);
    $("dRealized").textContent = fmt(a.realized_today);
    $("dRealized").className    = "stat-num " + cls(a.realized_today);

    renderPositions("dashPositions", a.positions, false);
    renderPositions("paperPositions", a.positions, true);
  }

  function renderPositions(targetId, positions, withSell) {
    const el = $(targetId);
    if (!el) return;
    if (!positions.length) { el.innerHTML = `<p class="empty">目前沒有持倉</p>`; return; }
    let h = `<table><thead><tr>
      <th>股票</th><th>股數</th><th>成本</th><th>現價</th><th>停損</th><th>未實現損益</th>
      ${withSell ? "<th></th>" : ""}</tr></thead><tbody>`;
    positions.forEach(p => {
      h += `<tr>
        <td>${p.stock_id}${p.is_live ? "" : ' <span class="muted" style="font-size:11px">(成本價)</span>'}</td>
        <td>${fmt(p.size)}</td>
        <td>${p.entry_price}</td>
        <td>${p.current}</td>
        <td class="muted">${p.stop_loss ?? "—"}</td>
        <td class="${cls(p.pnl)}">${fmt(p.pnl)} (${pct(p.pnl_pct)})</td>
        ${withSell ? `<td><button class="btn-sell" onclick="App.quickSell('${p.stock_id}',${p.current})">賣出</button></td>` : ""}
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table>";
  }

  // ---- 下單 ----
  async function autofillPrice() {
    const stock = $("orderStock").value.trim();
    if (!stock) return;
    const msg = $("orderMsg");
    msg.textContent = "查詢即時報價…"; msg.className = "msg";
    const r = await api("/api/price/" + stock);
    if (r.price) { $("orderPrice").value = r.price; msg.textContent = ""; }
    else { msg.textContent = "查無即時報價（非交易時間？可手動輸入）"; msg.className = "msg err"; }
  }

  async function buy() {
    const body = {
      stock_id: $("orderStock").value.trim(),
      price: parseFloat($("orderPrice").value),
      size: parseInt($("orderSize").value),
    };
    if (!body.stock_id || !body.price || !body.size) {
      return showMsg("orderMsg", "請完整填寫股票、價格、股數", false);
    }
    const r = await post("/api/buy", body);
    showMsg("orderMsg", r.msg, r.ok);
    if (r.ok) loadAccount();
  }

  async function quickSell(stock, price) {
    const reason = prompt(
      `賣出 ${stock} @ ${price}\n\n請誠實填寫出場原因（影響紀律分數）：\n` +
      `SIGNAL=訊號出場  STOP_LOSS=停損  EOD=收盤平倉  MANUAL=隨意手動`,
      "SIGNAL"
    );
    if (reason === null) return;
    const r = await post("/api/sell", { stock_id: stock, price: price, reason: reason.trim().toUpperCase() });
    if (r.ok) { loadAccount(); loadJournal(); }
    else alert(r.msg);
  }

  async function resetAccount() {
    if (!confirm("確定重置帳戶？這會清空資金與部位（交易日誌保留）")) return;
    const r = await post("/api/reset");
    alert(r.msg); loadAccount(); loadJournal();
  }

  function showMsg(id, text, ok) {
    const el = $(id); el.textContent = text;
    el.className = "msg " + (ok ? "ok" : "err");
    if (ok) setTimeout(() => { el.textContent = ""; }, 3000);
  }

  // ---- 交易日誌 ----
  async function loadJournal() {
    const data = await api("/api/journal");
    const el = $("journalTable");
    if (!data.length) { el.innerHTML = `<p class="empty">尚無交易紀錄</p>`; return; }
    const rmap = { SIGNAL:"訊號", STOP_LOSS:"停損", EOD:"收盤", MANUAL:"手動" };
    let h = `<table><thead><tr>
      <th>編號</th><th>股票</th><th>進場</th><th>出場</th><th>股數</th><th>淨損益</th><th>原因</th>
      </tr></thead><tbody>`;
    data.slice(0, 50).forEach(r => {
      h += `<tr>
        <td>${r.trade_id}</td><td>${r.stock_id}</td>
        <td class="muted">${r.entry_price}</td>
        <td class="muted">${r.exit_price}</td>
        <td>${fmt(r.size)}</td>
        <td class="${cls(r.net_pnl)}">${fmt(r.net_pnl)}</td>
        <td><span class="muted">${rmap[r.exit_reason] || r.exit_reason}</span></td>
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table>";
  }

  // ---- 盤前掃描 ----
  async function runScan() {
    const btn = $("scanBtn"), box = $("scanResult");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 掃描中';
    box.innerHTML = `<p class="empty"><span class="spinner"></span> 逐檔抓資料計算中，請稍候…</p>`;
    try {
      const d = await api("/api/scan");
      renderScan(d);
    } catch (e) {
      box.innerHTML = `<p class="empty">掃描失敗：${e}</p>`;
    }
    btn.disabled = false; btn.textContent = "開始掃描";
  }

  function sigTag(s) {
    if (!s) return `<span class="tag tag-hold">—</span>`;
    if (s === "BUY")   return `<span class="tag tag-buy">買</span>`;
    if (s === "SELL")  return `<span class="tag tag-sell">賣</span>`;
    if (s === "WATCH") return `<span class="tag tag-watch">關注</span>`;
    return `<span class="tag tag-hold">${s.includes("HOLD")?"持有":s}</span>`;
  }

  function renderScan(d) {
    const box = $("scanResult");
    let cand = "";
    if (d.candidates.length) {
      cand = `<div class="card cand-card">
        <h2>今日買入候選 (${d.candidates.length})</h2>` +
        d.candidates.map(c =>
          `<div class="cand-item"><strong>${c.id}</strong> ${c.name}　收盤 ${c.close}　RSI ${c.rsi ?? "—"}　共識 <strong class="up">${c.consensus}</strong></div>`
        ).join("") + `</div>`;
    } else {
      cand = `<p class="hint">今日無明確買入共識訊號（這很正常，別硬找單做）</p>`;
    }

    let h = `<table><thead><tr>
      <th>代號</th><th>名稱</th><th>收盤</th><th>RSI</th><th>BB%</th><th>量比</th>
      <th>均線</th><th>RSI</th><th>布林</th><th>共識</th></tr></thead><tbody>`;
    d.rows.forEach(r => {
      const cc = r.consensus && r.consensus.includes("BUY") ? "up"
               : r.consensus === "SELL" ? "down" : "muted";
      h += `<tr>
        <td>${r.id}</td><td>${r.name}</td>
        <td>${r.close ?? "—"}</td>
        <td>${r.rsi ?? "—"}</td>
        <td>${r.bb_pct ?? "—"}</td>
        <td>${r.vol_ratio ?? "—"}</td>
        <td>${sigTag(r.ma_signal)}</td>
        <td>${sigTag(r.rsi_signal)}</td>
        <td>${sigTag(r.bb_signal)}</td>
        <td class="${cc}"><strong>${r.consensus || "—"}</strong></td>
      </tr>`;
    });
    box.innerHTML = cand + `<div class="card" style="padding:0;overflow:hidden">${h}</tbody></table></div>
      <p class="hint" style="margin-top:8px">資料日期：${d.date}　訊號僅供參考，最終決策與紀律在你</p>`;
  }

  // ---- 紀律計分 ----
  async function loadDiscipline() {
    const d = await api("/api/discipline");
    renderScorecard(d.scorecard);
    renderBenchmark(d.benchmark);
  }

  function gradeColor(s) {
    if (s >= 90) return "#2f9e44";
    if (s >= 80) return "#37b24d";
    if (s >= 70) return "#1971c2";
    if (s >= 60) return "#f08c00";
    return "#e03131";
  }
  function gradeLetter(s) {
    if (s >= 90) return "A+"; if (s >= 80) return "A";
    if (s >= 70) return "B";  if (s >= 60) return "C"; return "D";
  }

  function renderScorecard(sc) {
    const box = $("scorecardBox");
    if (!sc || !sc.total_score && sc.total_score !== 0) {
      box.innerHTML = `<p class="empty">尚無交易紀錄，先到「紙盤交易」累積幾筆</p>`; return;
    }
    const color = gradeColor(sc.total_score);
    const notes = {
      "停損紀律":   `破戒 ${sc.stop_breaches} 次`,
      "當沖紀律":   `當日平倉率`,
      "不亂凹系統": `手動干預 ${sc.manual_exits} 次`,
      "不過度交易": `平均 ${sc.avg_per_day} 筆/日`,
      "不報復交易": `追單 ${sc.revenge_trades} 次`,
    };
    let dims = "";
    for (const [name, score] of Object.entries(sc.scores)) {
      const c = gradeColor(score);
      dims += `<div class="dim-row">
        <div class="dim-name">${name}</div>
        <div class="dim-bar"><div class="dim-fill" style="width:${score}%;background:${c}"></div></div>
        <div class="dim-score" style="color:${c}">${score} ${gradeLetter(score)}</div>
        <div class="dim-note">${notes[name] || ""}</div>
      </div>`;
    }
    const deg = (sc.total_score / 100) * 360;
    box.innerHTML = `
      <div class="score-hero">
        <div class="score-ring" style="background:conic-gradient(${color} ${deg}deg, #eef0f4 0deg)">
          <div class="score-ring-inner">
            <span class="num" style="color:${color}">${sc.total_score}</span>
            <span class="grade">${gradeLetter(sc.total_score)} 級</span>
          </div>
        </div>
        <div class="score-hero-meta">
          <strong>紀律總分 ${sc.total_score}/100</strong>
          <div class="muted" style="font-size:13px">共 ${sc.total_trades} 筆交易 · ${sc.active_days} 個交易日</div>
        </div>
      </div>
      ${dims}`;
  }

  function renderBenchmark(b) {
    const box = $("benchmarkBox");
    if (!b || !b.trade_count) { box.innerHTML = `<p class="empty">尚無交易紀錄</p>`; return; }
    let h = `
      <div class="bench-row"><span>你的紙盤交易</span><span class="v ${cls(b.paper_return)}">${pct(b.paper_return)}</span></div>`;
    if (b.bench_return != null) {
      h += `
      <div class="bench-row"><span>買 ${b.benchmark_id} 放著不動</span><span class="v ${cls(b.bench_return)}">${pct(b.bench_return)}</span></div>
      <div class="bench-row"><span>你的超額報酬</span><span class="v ${cls(b.excess)}">${pct(b.excess)}</span></div>`;
      const win = b.excess >= 0;
      h += `<div class="bench-verdict ${win ? "win" : "lose"}">${
        win ? "✓ 這段期間你贏過大盤——是技術還是運氣？保持謙卑。"
            : "✗ 跑輸大盤。這不丟臉，多數專業經理人也輸。紙盤的價值在練紀律。"
      }</div>`;
    }
    h += `<p class="hint" style="margin-top:10px">期間：${b.start} ~ ${b.end}</p>`;
    box.innerHTML = h;
  }

  // ---- 回測 ----
  let _strategies = [];
  async function initStrategies() {
    _strategies = await api("/api/strategies");
    const sel = $("btStrategy");
    sel.innerHTML = _strategies.map(s =>
      `<option value="${s.key}"${s.key==="ma_filtered"?" selected":""}>${s.label}</option>`).join("");
    sel.onchange = renderStrategyDesc;
    renderStrategyDesc();
  }
  function renderStrategyDesc() {
    const s = _strategies.find(x => x.key === $("btStrategy").value);
    const box = $("btStrategyDesc");
    if (box && s) box.innerHTML = `<strong>${s.label}</strong><span>${s.desc || ""}</span>`;
  }

  async function runBacktest() {
    const btn = $("btBtn"), box = $("backtestResult");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 回測中';
    box.innerHTML = "";
    const body = {
      stock: $("btStock").value.trim(),
      strategy: $("btStrategy").value,
      start: $("btStart").value,
      end: $("btEnd").value,
    };
    const r = await post("/api/backtest", body);
    if (!r.ok) {
      box.innerHTML = `<p class="empty">${r.msg}</p>`;
    } else {
      const m = r.metrics;
      const card = (label, val, c) =>
        `<div class="metric"><div class="metric-label">${label}</div><div class="metric-val ${c||""}">${val}</div></div>`;
      box.innerHTML = `<div class="metrics-grid">
        ${card("總報酬率", pct(m.total_return_pct), cls(m.total_return_pct))}
        ${card("夏普比率", m.sharpe_ratio ?? "N/A")}
        ${card("最大回撤", m.max_drawdown_pct + "%")}
        ${card("勝率", m.win_rate_pct + "%")}
        ${card("獲利因子", m.profit_factor)}
        ${card("交易次數", m.total_trades)}
      </div>
      <p class="hint" style="margin-top:12px">${m.bars} 根K棒　|　提醒：回測亮眼≠未來有效，務必再跑 Walk-Forward 驗證</p>`;
    }
    btn.disabled = false; btn.textContent = "執行回測";
  }

  // ---- 設定：初始資金 ----
  async function loadSettings() {
    const s = await api("/api/settings");
    $("setCapital").value = s.initial_capital;
    loadWatchlistEditor();
  }
  function setCapInput(v) { $("setCapital").value = v; }

  async function saveCapital() {
    const cap = parseFloat($("setCapital").value);
    if (!cap || cap < 10000) return showMsg("capMsg", "初始資金需至少 10,000", false);
    if (!confirm(`將初始資金設為 ${cap.toLocaleString("zh-TW")} 元？\n這會重置帳戶（清空持倉與資金）。`)) return;
    const r = await post("/api/settings", { initial_capital: cap });
    showMsg("capMsg", r.msg, r.ok);
    if (r.ok) loadAccount();
  }

  // ---- 設定：追蹤清單 ----
  async function loadWatchlistEditor() {
    const wl = await api("/api/watchlist");
    $("watchCount").textContent = `共 ${wl.length} 支`;
    const el = $("watchlistTable");
    if (!wl.length) { el.innerHTML = `<p class="empty">清單是空的，新增第一支股票吧</p>`; return; }
    let h = `<table><thead><tr><th>代號</th><th>名稱</th><th>產業</th><th></th></tr></thead><tbody>`;
    wl.forEach(s => {
      h += `<tr>
        <td>${s.id}</td><td>${s.name}</td>
        <td class="muted">${s.sector || "—"}</td>
        <td><button class="btn-sell" onclick="App.delStock('${s.id}')">移除</button></td>
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table>";
  }

  async function addStock() {
    const body = {
      id: $("addStockId").value.trim(),
      name: $("addStockName").value.trim(),
      sector: $("addStockSector").value.trim(),
    };
    if (!body.id) return showMsg("watchMsg", "請輸入股票代號", false);
    showMsg("watchMsg", "新增中（查詢股票名稱）…", true);
    const r = await post("/api/watchlist", body);
    showMsg("watchMsg", r.msg, r.ok);
    if (r.ok) {
      $("addStockId").value = ""; $("addStockName").value = ""; $("addStockSector").value = "";
      loadWatchlistEditor();
    }
  }

  async function delStock(sid) {
    if (!confirm(`從追蹤清單移除 ${sid}？`)) return;
    const r = await fetch("/api/watchlist/" + sid, { method: "DELETE" }).then(x => x.json());
    showMsg("watchMsg", r.msg, r.ok);
    if (r.ok) loadWatchlistEditor();
  }

  // ---- 初始化 ----
  function init() {
    initTabs();
    loadAccount();
    initStrategies();
    const chip = $("dateChip");
    if (chip) {
      const d = new Date();
      chip.textContent = `${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,"0")}/${String(d.getDate()).padStart(2,"0")}`;
    }
  }

  return { init, loadAccount, loadJournal, runScan, buy, quickSell, autofillPrice,
           resetAccount, loadDiscipline, runBacktest,
           loadSettings, setCapInput, saveCapital, addStock, delStock };
})();

document.addEventListener("DOMContentLoaded", App.init);
