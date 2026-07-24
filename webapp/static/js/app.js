/* PaperTrade TW — 前端邏輯（2026 重設計） */
const App = (() => {

  // ═══ 工具 ═══════════════════════════════════════════════
  const $  = (id) => document.getElementById(id);
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("zh-TW"));
  const pct = (n) => (n == null ? "—" : (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%");
  const cls = (n) => (n > 0 ? "up" : n < 0 ? "down" : "");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));

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

  // ═══ Toast ══════════════════════════════════════════════
  function toast(msg, ok = true) {
    const stack = $("toastStack");
    const el = document.createElement("div");
    el.className = "toast " + (ok ? "ok" : "err");
    el.style.pointerEvents = "auto";
    el.textContent = msg;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      el.addEventListener("animationend", () => el.remove(), { once: true });
    }, 3200);
  }

  // ═══ Modal ══════════════════════════════════════════════
  function openModal(html) {
    $("modalBox").innerHTML = html;
    $("modalBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeModal() {
    $("modalBackdrop").hidden = true;
    $("modalBox").innerHTML = "";
    document.body.style.overflow = "";
  }
  function confirmModal({ title, body, okText = "確定", danger = false }) {
    return new Promise(resolve => {
      openModal(`
        <h3>${esc(title)}</h3>
        <p class="m-sub">${body}</p>
        <div class="m-actions">
          <button class="btn ghost" id="mCancel">取消</button>
          <button class="btn ${danger ? "danger-ghost" : "primary"}" id="mOk">${esc(okText)}</button>
        </div>`);
      $("mCancel").onclick = () => { closeModal(); resolve(false); };
      $("mOk").onclick     = () => { closeModal(); resolve(true); };
    });
  }

  // ═══ 主題 ══════════════════════════════════════════════
  function initTheme() {
    const saved = localStorage.getItem("pt-theme");
    if (saved) document.documentElement.dataset.theme = saved;
    $("themeToggle").onclick = () => {
      const cur = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = cur;
      localStorage.setItem("pt-theme", cur);
    };
  }

  // ═══ 分頁 ══════════════════════════════════════════════
  const TITLES = {
    dashboard: "總覽", scan: "盤前掃描", paper: "紙盤交易",
    discipline: "紀律計分", backtest: "策略回測", settings: "設定",
  };
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
  function onTab(name) {
    $("pageTitle").textContent = TITLES[name] || "";
    if (name === "dashboard") { loadAccount(); loadSparkline(); }
    if (name === "paper")     { loadAccount(); loadJournal(); }
    if (name === "discipline") loadDiscipline();
    if (name === "settings")   loadSettings();
  }

  // ═══ 帳戶 / 部位 ════════════════════════════════════════
  async function loadAccount() {
    const a = await api("/api/account");
    $("pillEquity").textContent = fmt(a.equity);
    $("pillReturn").textContent = pct(a.total_return);
    $("pillReturn").className = "pill-value num " + cls(a.total_return);

    $("dCash").textContent     = fmt(a.cash);
    $("dPosVal").textContent   = fmt(a.position_value);
    $("dEquity").textContent   = fmt(a.equity);
    const delta = $("dEquityDelta");
    delta.textContent = `${pct(a.total_return)} vs 初始 ${fmt(a.start_capital)}`;
    delta.className = "stat-delta num " + cls(a.total_return);
    $("dRealized").textContent = (a.realized_today > 0 ? "+" : "") + fmt(a.realized_today);
    $("dRealized").className   = "stat-num num " + cls(a.realized_today);

    renderPositions("dashPositions", a.positions, false);
    renderPositions("paperPositions", a.positions, true);
  }

  function renderPositions(targetId, positions, withSell) {
    const el = $(targetId);
    if (!el) return;
    if (!positions.length) { el.innerHTML = `<p class="empty">目前沒有持倉</p>`; return; }
    let h = `<div class="table-wrap"><table><thead><tr>
      <th>股票</th><th class="r">股數</th><th class="r">成本</th><th class="r">現價</th>
      <th class="r">停損</th><th class="r">未實現損益</th>
      ${withSell ? "<th></th>" : ""}</tr></thead><tbody>`;
    positions.forEach(p => {
      h += `<tr>
        <td><strong>${esc(p.stock_id)}</strong>${p.is_live ? "" : ' <span class="muted" style="font-size:11px">(成本價)</span>'}</td>
        <td class="r">${fmt(p.size)}</td>
        <td class="r">${p.entry_price}</td>
        <td class="r">${p.current}</td>
        <td class="r muted">${p.stop_loss ?? "—"}</td>
        <td class="r ${cls(p.pnl)}">${p.pnl > 0 ? "+" : ""}${fmt(p.pnl)} (${pct(p.pnl_pct)})</td>
        ${withSell ? `<td class="r"><button class="btn sell sm" onclick="App.sellDialog('${esc(p.stock_id)}',${p.current})">賣出</button></td>` : ""}
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table></div>";
  }

  // ═══ 累計損益 sparkline ═════════════════════════════════
  async function loadSparkline() {
    const data = await api("/api/journal");   // 最新在前
    const wrap = $("sparkWrap");
    if (!data.length) {
      wrap.innerHTML = `<p class="empty">尚無平倉紀錄</p>`;
      $("sparkMeta").textContent = "";
      return;
    }
    const recs = data.slice().reverse();      // 時間正序
    let cum = 0;
    const pts = recs.map(r => ({ t: r.exit_time, pnl: r.net_pnl, cum: (cum += r.net_pnl) }));
    $("sparkMeta").textContent = `${pts.length} 筆平倉 · 累計 ${cum >= 0 ? "+" : ""}${fmt(Math.round(cum))}`;

    const W = 560, H = 160, PAD = 10;
    const vals = pts.map(p => p.cum).concat([0]);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = (max - min) || 1;
    const x = i => PAD + (W - 2 * PAD) * (pts.length === 1 ? 0.5 : i / (pts.length - 1));
    const y = v => PAD + (H - 2 * PAD) * (1 - (v - min) / span);

    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.cum).toFixed(1)}`).join(" ");
    const area = `${line} L${x(pts.length - 1).toFixed(1)},${y(0).toFixed(1)} L${x(0).toFixed(1)},${y(0).toFixed(1)} Z`;
    const lastUp = cum >= 0;
    const col = lastUp ? "var(--up)" : "var(--down)";

    wrap.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" id="sparkSvg">
        <defs>
          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${lastUp ? "#e66767" : "#0ca30c"}" stop-opacity=".22"/>
            <stop offset="1" stop-color="${lastUp ? "#e66767" : "#0ca30c"}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <line x1="${PAD}" x2="${W - PAD}" y1="${y(0)}" y2="${y(0)}" stroke="var(--grid)" stroke-width="1" stroke-dasharray="3 4"/>
        <path d="${area}" fill="url(#sparkFill)"/>
        <path d="${line}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle id="sparkDot" r="4" fill="${col}" stroke="var(--surface)" stroke-width="2" opacity="0"/>
      </svg>
      <div class="spark-tip" id="sparkTip"></div>`;

    // hover：最近點 tooltip
    const svg = $("sparkSvg"), dot = $("sparkDot"), tip = $("sparkTip");
    svg.addEventListener("mousemove", ev => {
      const rect = svg.getBoundingClientRect();
      const rel = (ev.clientX - rect.left) / rect.width * W;
      let i = Math.round((rel - PAD) / (W - 2 * PAD) * (pts.length - 1));
      i = Math.max(0, Math.min(pts.length - 1, i));
      const p = pts[i];
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(p.cum));
      dot.setAttribute("opacity", "1");
      tip.innerHTML = `<span class="t-label">#${i + 1} ${esc((p.t || "").slice(0, 10))}</span>` +
        `<strong class="num ${cls(p.cum)}">${p.cum >= 0 ? "+" : ""}${fmt(Math.round(p.cum))}</strong>`;
      tip.style.left = (x(i) / W * rect.width) + "px";
      tip.style.top  = (y(p.cum) / H * rect.height) + "px";
      tip.classList.add("show");
    });
    svg.addEventListener("mouseleave", () => {
      dot.setAttribute("opacity", "0");
      tip.classList.remove("show");
    });
  }

  // ═══ 下單 ══════════════════════════════════════════════
  async function autofillPrice() {
    const stock = $("orderStock").value.trim();
    if (!stock) return;
    const r = await api("/api/price/" + encodeURIComponent(stock));
    if (r.price) { $("orderPrice").value = r.price; }
    else toast("查無即時報價（非交易時間？可手動輸入）", false);
  }

  async function buy() {
    const body = {
      stock_id: $("orderStock").value.trim(),
      price: parseFloat($("orderPrice").value),
      size: parseInt($("orderSize").value),
    };
    if (!body.stock_id || !(body.price > 0) || !(body.size > 0)) {
      return toast("請完整填寫股票、正數價格與股數", false);
    }
    const r = await post("/api/buy", body);
    toast(r.msg, r.ok);
    if (r.ok) { loadAccount(); }
  }

  // 賣出 dialog：出場原因會影響紀律分數，用卡片選擇取代 prompt
  const REASONS = [
    { key: "SIGNAL",    label: "訊號出場", desc: "策略訊號正常出場" },
    { key: "STOP_LOSS", label: "停損",     desc: "觸及停損價，果斷砍" },
    { key: "EOD",       label: "收盤平倉", desc: "當沖收盤前結清" },
    { key: "MANUAL",    label: "手動干預", desc: "憑感覺（會扣紀律分）" },
  ];
  function sellDialog(stockId, price) {
    let reason = "SIGNAL";
    openModal(`
      <h3>賣出 ${esc(stockId)}</h3>
      <p class="m-sub">請誠實選擇出場原因——這會計入紀律計分卡。</p>
      <label>成交價格
        <input id="mSellPrice" type="number" step="0.01" min="0.01" value="${price}">
      </label>
      <div class="reason-grid">
        ${REASONS.map(r => `
          <button class="reason-opt${r.key === "SIGNAL" ? " sel" : ""}" data-r="${r.key}">
            <strong>${r.label}</strong><span>${r.desc}</span>
          </button>`).join("")}
      </div>
      <div class="m-actions">
        <button class="btn ghost" id="mCancel">取消</button>
        <button class="btn sell" id="mOk">確認賣出</button>
      </div>`);
    document.querySelectorAll(".reason-opt").forEach(b => {
      b.onclick = () => {
        document.querySelectorAll(".reason-opt").forEach(x => x.classList.remove("sel"));
        b.classList.add("sel");
        reason = b.dataset.r;
      };
    });
    $("mCancel").onclick = closeModal;
    $("mOk").onclick = async () => {
      const p = parseFloat($("mSellPrice").value);
      if (!(p > 0)) return toast("價格必須為正數", false);
      closeModal();
      const r = await post("/api/sell", { stock_id: stockId, price: p, reason });
      toast(r.msg, r.ok);
      if (r.ok) { loadAccount(); loadJournal(); loadSparkline(); }
    };
  }

  async function resetAccount() {
    const ok = await confirmModal({
      title: "重置帳戶",
      body: "這會清空資金與持倉（交易日誌保留）。確定重置？",
      okText: "重置", danger: true,
    });
    if (!ok) return;
    const r = await post("/api/reset");
    toast(r.msg, r.ok);
    loadAccount(); loadJournal(); loadSparkline();
  }

  // ═══ 交易日誌 ══════════════════════════════════════════
  async function loadJournal() {
    const data = await api("/api/journal");
    const el = $("journalTable");
    if (!data.length) { el.innerHTML = `<p class="empty">尚無交易紀錄</p>`; return; }
    const rmap = { SIGNAL: "訊號", STOP_LOSS: "停損", EOD: "收盤", MANUAL: "手動" };
    let h = `<div class="table-wrap"><table><thead><tr>
      <th>編號</th><th>股票</th><th class="r">進場</th><th class="r">出場</th>
      <th class="r">股數</th><th class="r">淨損益</th><th>原因</th>
      </tr></thead><tbody>`;
    data.slice(0, 50).forEach(r => {
      h += `<tr>
        <td class="muted">${esc(r.trade_id)}</td><td><strong>${esc(r.stock_id)}</strong></td>
        <td class="r muted">${r.entry_price}</td>
        <td class="r muted">${r.exit_price}</td>
        <td class="r">${fmt(r.size)}</td>
        <td class="r ${cls(r.net_pnl)}">${r.net_pnl > 0 ? "+" : ""}${fmt(r.net_pnl)}</td>
        <td><span class="muted">${rmap[r.exit_reason] || esc(r.exit_reason)}</span></td>
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table></div>";
  }

  // ═══ 盤前掃描 ══════════════════════════════════════════
  async function runScan() {
    const btn = $("scanBtn"), box = $("scanResult");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 掃描中';
    box.innerHTML = `<p class="empty"><span class="spinner"></span> 逐檔抓資料計算中，請稍候…</p>`;
    try {
      const d = await api("/api/scan");
      renderScan(d);
    } catch (e) {
      box.innerHTML = `<p class="empty">掃描失敗：${esc(e)}</p>`;
    }
    btn.disabled = false; btn.textContent = "開始掃描";
  }

  function sigTag(s) {
    if (!s) return `<span class="tag tag-hold">—</span>`;
    if (s === "BUY")   return `<span class="tag tag-buy">買</span>`;
    if (s === "SELL")  return `<span class="tag tag-sell">賣</span>`;
    if (s === "WATCH") return `<span class="tag tag-watch">關注</span>`;
    return `<span class="tag tag-hold">${s.includes("HOLD") ? "持有" : esc(s)}</span>`;
  }

  function renderScan(d) {
    const box = $("scanResult");
    let cand = "";
    if (d.candidates.length) {
      cand = `<div class="cand-strip">` +
        d.candidates.map(c =>
          `<div class="cand-item"><strong>${esc(c.id)}</strong> ${esc(c.name)}
           <span class="muted num">收盤 ${c.close}</span>
           <strong class="num">${esc(c.consensus)}</strong></div>`).join("") + `</div>`;
    } else {
      cand = `<p class="hint">今日無明確買入共識訊號（這很正常，別硬找單做）。</p>`;
    }

    let h = `<div class="table-wrap"><table><thead><tr>
      <th>代號</th><th>名稱</th><th class="r">收盤</th><th class="r">RSI</th>
      <th class="r">BB%</th><th class="r">量比</th>
      <th>均線</th><th>RSI</th><th>布林</th><th>共識</th></tr></thead><tbody>`;
    d.rows.forEach(r => {
      const cc = r.consensus && r.consensus.includes("BUY") ? "up"
               : r.consensus === "SELL" ? "down" : "muted";
      h += `<tr>
        <td><strong>${esc(r.id)}</strong></td><td>${esc(r.name)}</td>
        <td class="r">${r.close ?? "—"}</td>
        <td class="r">${r.rsi ?? "—"}</td>
        <td class="r">${r.bb_pct ?? "—"}</td>
        <td class="r">${r.vol_ratio ?? "—"}</td>
        <td>${sigTag(r.ma_signal)}</td>
        <td>${sigTag(r.rsi_signal)}</td>
        <td>${sigTag(r.bb_signal)}</td>
        <td class="${cc}"><strong>${esc(r.consensus || "—")}</strong></td>
      </tr>`;
    });
    box.innerHTML = cand + h + `</tbody></table></div>
      <p class="hint" style="margin-top:10px">資料日期：${esc(d.date)} · 共識訊號僅供參考、未經回測驗證。</p>`;
  }

  // ═══ 紀律計分 ══════════════════════════════════════════
  async function loadDiscipline() {
    const d = await api("/api/discipline");
    renderScorecard(d.scorecard);
    renderBenchmark(d.benchmark);
  }

  function gradeColor(s) {
    if (s >= 80) return "var(--down)";       /* 高分安全 → 綠 */
    if (s >= 60) return "var(--warn)";
    return "var(--up)";
  }
  function gradeLetter(s) {
    if (s >= 90) return "A+"; if (s >= 80) return "A";
    if (s >= 70) return "B";  if (s >= 60) return "C"; return "D";
  }

  function renderScorecard(sc) {
    const box = $("scorecardBox");
    if (!sc || (!sc.total_score && sc.total_score !== 0)) {
      box.innerHTML = `<p class="empty">尚無交易紀錄，先到「紙盤交易」累積幾筆。</p>`; return;
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
        <div class="dim-name">${esc(name)}</div>
        <div class="dim-bar"><div class="dim-fill" style="width:${score}%;background:${c}"></div></div>
        <div class="dim-score" style="color:${c}">${score} ${gradeLetter(score)}</div>
        <div class="dim-note">${notes[name] || ""}</div>
      </div>`;
    }
    const deg = (sc.total_score / 100) * 360;
    box.innerHTML = `
      <div class="score-hero">
        <div class="score-ring" style="background:conic-gradient(${color} ${deg}deg, var(--surface-2) 0deg)">
          <div class="score-ring-inner">
            <span class="n num" style="color:${color}">${sc.total_score}</span>
            <span class="g">${gradeLetter(sc.total_score)} 級</span>
          </div>
        </div>
        <div class="score-hero-meta">
          <strong>紀律總分 ${sc.total_score} / 100</strong>
          <div class="sub">共 ${sc.total_trades} 筆交易 · ${sc.active_days} 個交易日</div>
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
      <div class="bench-row"><span>買 ${esc(b.benchmark_id)} 放著不動</span><span class="v ${cls(b.bench_return)}">${pct(b.bench_return)}</span></div>
      <div class="bench-row"><span>你的超額報酬</span><span class="v ${cls(b.excess)}">${pct(b.excess)}</span></div>`;
      const win = b.excess >= 0;
      h += `<div class="bench-verdict ${win ? "win" : "lose"}">${
        win ? "✓ 這段期間你贏過大盤——是技術還是運氣？保持謙卑。"
            : "✗ 跑輸大盤。這不丟臉，多數專業經理人也輸。紙盤的價值在練紀律。"
      }</div>`;
    }
    h += `<p class="hint" style="margin-top:12px">期間：${esc(b.start)} ~ ${esc(b.end)} · ${b.trade_count} 筆交易</p>`;
    box.innerHTML = h;
  }

  // ═══ 回測 ══════════════════════════════════════════════
  let _strategies = [];
  async function initStrategies() {
    _strategies = await api("/api/strategies");
    const sel = $("btStrategy");
    sel.innerHTML = _strategies.map(s =>
      `<option value="${esc(s.key)}"${s.key === "ma_filtered" ? " selected" : ""}>${esc(s.label)}</option>`).join("");
    sel.onchange = renderStrategyDesc;
    renderStrategyDesc();
  }
  function renderStrategyDesc() {
    const s = _strategies.find(x => x.key === $("btStrategy").value);
    if (s) $("btStrategyDesc").innerHTML = `<strong>${esc(s.label)}</strong><span>${esc(s.desc || "")}</span>`;
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
      box.innerHTML = `<p class="empty">${esc(r.msg)}</p>`;
    } else {
      const m = r.metrics;
      const card = (label, val, c) =>
        `<div class="metric"><div class="metric-label">${label}</div><div class="metric-val ${c || ""}">${val}</div></div>`;
      box.innerHTML = `<div class="metrics-grid">
        ${card("總報酬率", pct(m.total_return_pct), cls(m.total_return_pct))}
        ${card("夏普比率", m.sharpe_ratio ?? "N/A")}
        ${card("最大回撤", m.max_drawdown_pct + "%")}
        ${card("勝率", m.win_rate_pct + "%")}
        ${card("獲利因子", m.profit_factor)}
        ${card("交易次數", m.total_trades)}
      </div>
      <p class="hint" style="margin-top:12px">${m.bars} 根 K 棒 · 回測亮眼 ≠ 未來有效，務必再跑 Walk-Forward / 樣本外驗證。</p>`;
    }
    btn.disabled = false; btn.textContent = "執行回測";
  }

  // ═══ 設定 ══════════════════════════════════════════════
  async function loadSettings() {
    const s = await api("/api/settings");
    $("setCapital").value = s.initial_capital;
    loadWatchlistEditor();
  }
  function setCapInput(v) { $("setCapital").value = v; }

  async function saveCapital() {
    const cap = parseFloat($("setCapital").value);
    if (!cap || cap < 10000) return toast("初始資金需至少 10,000", false);
    const ok = await confirmModal({
      title: "變更初始資金",
      body: `將初始資金設為 <strong>${cap.toLocaleString("zh-TW")}</strong> 元？<br>這會重置帳戶（清空持倉與資金）。`,
      okText: "套用並重置",
    });
    if (!ok) return;
    const r = await post("/api/settings", { initial_capital: cap });
    toast(r.msg, r.ok);
    if (r.ok) loadAccount();
  }

  async function loadWatchlistEditor() {
    const wl = await api("/api/watchlist");
    $("watchCount").textContent = `共 ${wl.length} 支`;
    const el = $("watchlistTable");
    if (!wl.length) { el.innerHTML = `<p class="empty">清單是空的，新增第一支股票吧。</p>`; return; }
    let h = `<div class="table-wrap"><table><thead><tr>
      <th>代號</th><th>名稱</th><th>產業</th><th></th></tr></thead><tbody>`;
    wl.forEach(s => {
      h += `<tr>
        <td><strong>${esc(s.id)}</strong></td><td>${esc(s.name)}</td>
        <td class="muted">${esc(s.sector || "—")}</td>
        <td class="r"><button class="btn ghost sm" onclick="App.delStock('${esc(s.id)}')">移除</button></td>
      </tr>`;
    });
    el.innerHTML = h + "</tbody></table></div>";
  }

  async function addStock() {
    const body = {
      id: $("addStockId").value.trim(),
      name: $("addStockName").value.trim(),
      sector: $("addStockSector").value.trim(),
    };
    if (!body.id) return toast("請輸入股票代號", false);
    const r = await post("/api/watchlist", body);
    toast(r.msg, r.ok);
    if (r.ok) {
      $("addStockId").value = ""; $("addStockName").value = ""; $("addStockSector").value = "";
      loadWatchlistEditor();
    }
  }

  async function delStock(sid) {
    const ok = await confirmModal({
      title: "移除追蹤",
      body: `從追蹤清單移除 <strong>${esc(sid)}</strong>？`,
      okText: "移除", danger: true,
    });
    if (!ok) return;
    const r = await fetch("/api/watchlist/" + encodeURIComponent(sid), { method: "DELETE" }).then(x => x.json());
    toast(r.msg, r.ok);
    if (r.ok) loadWatchlistEditor();
  }

  // ═══ 初始化 ════════════════════════════════════════════
  function init() {
    initTheme();
    initTabs();
    loadAccount();
    loadSparkline();
    initStrategies();
    const d = new Date();
    $("dateChip").textContent =
      `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
    // Esc 關閉 modal；點背景關閉
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
    $("modalBackdrop").addEventListener("click", e => {
      if (e.target === $("modalBackdrop")) closeModal();
    });
  }

  return { init, loadAccount, loadJournal, runScan, buy, sellDialog, autofillPrice,
           resetAccount, loadDiscipline, runBacktest,
           loadSettings, setCapInput, saveCapital, addStock, delStock };
})();

document.addEventListener("DOMContentLoaded", App.init);
