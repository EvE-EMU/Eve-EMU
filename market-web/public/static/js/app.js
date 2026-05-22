/**
 * EVE-EMU market tools SPA (path-based routes, Adam4EVE / isk.gg layout).
 */

const API = "/api/market/v1";

let meta = null;

async function api(path, options = {}) {
  const headers = { Accept: "application/json" };
  const init = { method: options.method || "GET", headers };
  if (options.body != null) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  const r = await fetch(`${API}${path}`, init);
  if (!r.ok) {
    let detail = "";
    try {
      const err = await r.json();
      detail = err.detail || err.error || "";
    } catch {
      /* ignore */
    }
    throw new Error(detail ? `${r.status} ${detail}` : `${r.status} ${path}`);
  }
  return r.json();
}

function fmtIsk(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const x = Number(n);
  if (x >= 1e12) return (x / 1e12).toFixed(2) + " T ISK";
  if (x >= 1e9) return (x / 1e9).toFixed(2) + " B ISK";
  if (x >= 1e6) return (x / 1e6).toFixed(2) + " M ISK";
  if (x >= 1e4) return (x / 1e3).toFixed(2) + " k ISK";
  return (
    x.toLocaleString(undefined, { maximumFractionDigits: 2 }) + " ISK"
  );
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return String(s).replace(/"/g, "&quot;");
}

function syncStatusHtml() {
  const s = meta?.sync;
  if (!s) return "";
  if (!s.esi_configured) {
    return "<p>ESI not configured — set <code>MARKET_INTERNAL_SECRET</code> and rebuild <code>aa-web</code>.</p>";
  }
  if (!s.cached_orders) {
    return '<p>No cached orders yet. Run structure sync: <code>POST /api/market/v1/sync/structure</code></p>';
  }
  const n = s.cached_orders.toLocaleString();
  const detail = s.last_structure_sync?.detail || "";
  return `<p><strong>${n}</strong> orders cached at WOMPSTAR${detail ? ` (${detail})` : ""}.</p>`;
}

function typeIcon(typeId, size = 32) {
  return `/api/market/v1/browser/icon/${typeId}?size=${size}`;
}

function typeIconImg(typeId, size = 32, extraClass = "") {
  const src = typeIcon(typeId, size);
  const fb = `https://image.eveonline.com/Type/${typeId}_${size >= 64 ? 64 : 32}.png`;
  const render = `https://images.evetech.net/types/${typeId}/render?size=${size}`;
  return `<img src="${src}" width="${size}" height="${size}" class="type-icon ${extraClass}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='${render}';this.addEventListener('error',()=>{this.src='${fb}'},{once:true})"/>`;
}

function fmtVol(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function chartLegendItem(color, label, cls = "") {
  return `<span class="chart-legend-item ${cls}"><span class="chart-swatch" style="background:${color}"></span>${label}</span>`;
}

function historyTooltipHtml(d) {
  return `<div class="chart-tip-date">${escapeHtml(d.day)}</div>
    <div class="chart-tip-row sell"><span>High</span><strong>${fmtIsk(d.highest)}</strong></div>
    <div class="chart-tip-row" style="color:#6eb5ff"><span>Average</span><strong>${fmtIsk(d.average)}</strong></div>
    <div class="chart-tip-row buy"><span>Low</span><strong>${fmtIsk(d.lowest)}</strong></div>
    <div class="chart-tip-row vol"><span>Volume</span><strong>${fmtVol(d.volume)}</strong></div>
    <div class="chart-tip-row dim"><span>Orders</span><strong>${fmtVol(d.order_count)}</strong></div>`;
}

function indexAtX(x, layout) {
  const { pad, step, count } = layout;
  if (count < 1) return -1;
  const i = Math.round((x - pad) / step);
  return Math.max(0, Math.min(count - 1, i));
}

function drawHistoryCharts(wrap, days, period, hoverIndex = -1) {
  const canvasPrice = wrap.querySelector("#mb-chart-price");
  const canvasVol = wrap.querySelector("#mb-chart-vol");
  const tooltip = wrap.querySelector("#mb-chart-tooltip");
  if (!canvasPrice || !canvasVol || !days?.length) return null;

  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - period);
  const slice = days.filter((d) => new Date(d.day) >= cutoff);
  if (!slice.length) return null;

  const labels = slice.map((d) => d.day.slice(5));
  const highs = slice.map((d) => d.highest);
  const lows = slice.map((d) => d.lowest);
  const avgs = slice.map((d) => d.average);
  const vols = slice.map((d) => d.volume);
  const pad = 36;
  const priceH = 180;
  const volH = 120;

  const drawCrosshair = (ctx, x, ch, bottomPad) => {
    ctx.strokeStyle = "rgba(232, 236, 241, 0.35)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 8);
    ctx.lineTo(x, ch - bottomPad);
    ctx.stroke();
    ctx.setLineDash([]);
  };

  const drawLineChart = (canvas, series, colors, hoverIdx) => {
    const ctx = canvas.getContext("2d");
    const dpr = devicePixelRatio;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = priceH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const cw = canvas.clientWidth;
    const ch = priceH;
    ctx.clearRect(0, 0, cw, ch);
    const all = series.flat();
    const min = Math.min(...all);
    const max = Math.max(...all);
    const range = max - min || 1;
    const step = (cw - pad * 2) / Math.max(slice.length - 1, 1);

    ctx.strokeStyle = "#1e2733";
    ctx.beginPath();
    ctx.moveTo(pad, ch - pad);
    ctx.lineTo(cw - pad, ch - pad);
    ctx.stroke();

    series.forEach((vals, si) => {
      ctx.strokeStyle = colors[si];
      ctx.lineWidth = hoverIdx >= 0 ? 1.25 : 1.5;
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = pad + i * step;
        const y = ch - pad - ((v - min) / range) * (ch - pad * 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      if (hoverIdx >= 0) {
        const x = pad + hoverIdx * step;
        const y = ch - pad - ((vals[hoverIdx] - min) / range) * (ch - pad * 2);
        ctx.fillStyle = colors[si];
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    if (hoverIdx >= 0) drawCrosshair(ctx, pad + hoverIdx * step, ch, pad);

    ctx.fillStyle = "#8b95a8";
    ctx.font = "10px Segoe UI, sans-serif";
    ctx.fillText(fmtIsk(max), 4, 12);
    ctx.fillText(fmtIsk(min), 4, ch - pad);
    if (labels.length) {
      ctx.fillText(labels[0], pad, ch - 6);
      ctx.fillText(labels[labels.length - 1], cw - pad - 40, ch - 6);
    }
    return { pad, step, count: slice.length, cw, ch };
  };

  const drawBars = (canvas, vals, hoverIdx) => {
    const ctx = canvas.getContext("2d");
    const dpr = devicePixelRatio;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = volH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const cw = canvas.clientWidth;
    const ch = volH;
    ctx.clearRect(0, 0, cw, ch);
    const max = Math.max(...vals, 1);
    const step = (cw - pad * 2) / Math.max(vals.length - 1, 1);
    const barW = Math.max(3, step * 0.65);

    vals.forEach((v, i) => {
      const x = pad + i * step - barW / 2;
      const bh = (v / max) * (ch - pad - 12);
      const y = ch - pad - bh;
      ctx.fillStyle = i === hoverIdx ? "#6eb5ff" : "#4a5568";
      ctx.fillRect(x, y, barW, bh);
    });

    if (hoverIdx >= 0) drawCrosshair(ctx, pad + hoverIdx * step, ch, pad);

    ctx.fillStyle = "#8b95a8";
    ctx.font = "10px Segoe UI, sans-serif";
    ctx.fillText(fmtVol(max), 4, 12);
    ctx.fillText("0", 4, ch - pad);
    if (labels.length) {
      ctx.fillText(labels[0], pad, ch - 6);
      ctx.fillText(labels[labels.length - 1], cw - pad - 40, ch - 6);
    }
    return { pad, step, count: slice.length, cw, ch };
  };

  const layout = drawLineChart(
    canvasPrice,
    [highs, avgs, lows],
    ["#e85d5d", "#6eb5ff", "#4dbb6a"],
    hoverIndex
  );
  drawBars(canvasVol, vols, hoverIndex);

  if (tooltip && hoverIndex >= 0 && slice[hoverIndex]) {
    tooltip.innerHTML = historyTooltipHtml(slice[hoverIndex]);
    tooltip.classList.remove("hidden");
  } else if (tooltip) {
    tooltip.classList.add("hidden");
  }

  return { slice, layout };
}

function hubSell(r) {
  return r.wompstar_sell ?? r.sell_price;
}
function hubBuy(r) {
  return r.wompstar_buy ?? r.buy_price;
}

function hubPriceColumns(includeWomp = true) {
  const cols = [
    {
      label: "Jita sell",
      sortKey: "jita_sell",
      class: "num sell",
      defaultSortDir: "desc",
      render: (r) => fmtIsk(r.jita_sell),
    },
    {
      label: "Jita buy",
      sortKey: "jita_buy",
      class: "num buy",
      defaultSortDir: "desc",
      render: (r) => fmtIsk(r.jita_buy),
    },
    {
      label: "Amarr sell",
      sortKey: "amarr_sell",
      class: "num sell",
      defaultSortDir: "desc",
      render: (r) => fmtIsk(r.amarr_sell),
    },
    {
      label: "Amarr buy",
      sortKey: "amarr_buy",
      class: "num buy",
      defaultSortDir: "desc",
      render: (r) => fmtIsk(r.amarr_buy),
    },
  ];
  if (includeWomp) {
    const hub = meta?.wompstar?.name || "WOMP";
    cols.push(
      {
        label: `${hub} sell`,
        sortKey: "wompstar_sell",
        sortValue: (r) => hubSell(r),
        class: "num sell",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(hubSell(r)),
      },
      {
        label: `${hub} buy`,
        sortKey: "wompstar_buy",
        sortValue: (r) => hubBuy(r),
        class: "num buy",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(hubBuy(r)),
      }
    );
  }
  return cols;
}

function drawHubGroupedChart(canvas, rows, side) {
  const isSell = side === "sell";
  const seriesKeys = isSell
    ? [
        ["jita_sell", "Jita"],
        ["amarr_sell", "Amarr"],
        ["womp", meta?.wompstar?.name?.split(" ")[0] || "WOMP"],
      ]
    : [
        ["jita_buy", "Jita"],
        ["amarr_buy", "Amarr"],
        ["womp", meta?.wompstar?.name?.split(" ")[0] || "WOMP"],
      ];
  const colors = ["#e85d5d", "#d4a84b", "#4dbb6a"];
  const slice = rows.slice(0, 14);
  if (!slice.length || !canvas) return;

  const labels = slice.map(
    (r) => (r.type_name || r.name || `T${r.type_id}`).slice(0, 18)
  );
  const pad = 44;
  const ch = 200;
  const ctx = canvas.getContext("2d");
  const dpr = devicePixelRatio;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = ch * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cw = canvas.clientWidth;
  ctx.clearRect(0, 0, cw, ch);

  const valsFor = (key, row) => {
    if (key === "womp") return isSell ? hubSell(row) : hubBuy(row);
    return row[key];
  };
  const all = slice.flatMap((r) =>
    seriesKeys.map(([k]) => Number(valsFor(k, r) || 0)).filter((v) => v > 0)
  );
  const max = Math.max(...all, 1);
  const groupW = (cw - pad * 2) / Math.max(slice.length, 1);
  const barW = Math.max(2, (groupW * 0.7) / seriesKeys.length);

  slice.forEach((row, gi) => {
    const gx = pad + gi * groupW + groupW * 0.15;
    seriesKeys.forEach(([key], si) => {
      const v = Number(valsFor(key, row) || 0);
      if (!v) return;
      const bh = (v / max) * (ch - pad - 20);
      const x = gx + si * barW;
      const y = ch - pad - bh;
      ctx.fillStyle = colors[si];
      ctx.fillRect(x, y, barW - 1, bh);
    });
    ctx.fillStyle = "#8b95a8";
    ctx.font = "9px Segoe UI, sans-serif";
    ctx.save();
    ctx.translate(gx + groupW * 0.2, ch - 4);
    ctx.rotate(-0.45);
    ctx.fillText(labels[gi], 0, 0);
    ctx.restore();
  });

  ctx.fillStyle = "#8b95a8";
  ctx.font = "10px Segoe UI, sans-serif";
  ctx.fillText(fmtIsk(max), 4, 12);
  seriesKeys.forEach(([, lab], si) => {
    ctx.fillStyle = colors[si];
    ctx.fillRect(cw - pad - 120 + si * 40, 8, 10, 10);
    ctx.fillStyle = "#c5cdd8";
    ctx.fillText(lab, cw - pad - 108 + si * 40, 17);
  });
}

function mountHubCompareCharts(container, rows) {
  if (!rows?.length) return;
  const sorted = [...rows].sort(
    (a, b) => Number(b.spread_isk ?? 0) - Number(a.spread_isk ?? 0)
  );
  container.innerHTML = `
    <div class="hub-charts-wrap">
      <p class="chart-section-title">Regional sell — top spreads at hub</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="hub-chart-sell"></canvas></div>
      <p class="chart-section-title">Regional buy</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="hub-chart-buy"></canvas></div>
    </div>`;
  const paint = () => {
    drawHubGroupedChart(container.querySelector("#hub-chart-sell"), sorted, "sell");
    drawHubGroupedChart(container.querySelector("#hub-chart-buy"), sorted, "buy");
  };
  paint();
  if (!container._hubResizeBound) {
    container._hubResizeBound = true;
    window.addEventListener("resize", paint);
  }
}

function bindHistoryChartHover(wrap) {
  if (wrap._chartHoverBound) return;
  wrap._chartHoverBound = true;

  const tooltip = wrap.querySelector("#mb-chart-tooltip");
  const chartsArea = wrap.querySelector(".mb-charts-area");
  const priceHost = wrap.querySelector(".chart-host-price");
  const volHost = wrap.querySelector(".chart-host-vol");
  let hoverIndex = -1;

  const positionTooltip = (e) => {
    if (!tooltip || hoverIndex < 0) return;
    const section = wrap.getBoundingClientRect();
    let left = e.clientX - section.left + 14;
    let top = e.clientY - section.top - 12;
    const tw = tooltip.offsetWidth || 200;
    if (left + tw > section.width - 8) left = e.clientX - section.left - tw - 14;
    if (top < 8) top = 8;
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  const onMove = (e, host) => {
    const canvas = host.querySelector("canvas");
    const st = wrap._chartState;
    if (!canvas || !st?.layout) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = indexAtX(x, st.layout);
    if (idx === hoverIndex) {
      positionTooltip(e);
      return;
    }
    hoverIndex = idx;
    const painted = drawHistoryCharts(wrap, st.days, st.period, hoverIndex);
    wrap._chartState = {
      days: st.days,
      period: st.period,
      hoverIndex: idx,
      layout: painted?.layout,
    };
    positionTooltip(e);
  };

  const onLeave = () => {
    hoverIndex = -1;
    const st = wrap._chartState;
    if (!st) return;
    st.hoverIndex = -1;
    drawHistoryCharts(wrap, st.days, st.period, -1);
  };

  [priceHost, volHost].forEach((host) => {
    if (!host) return;
    host.addEventListener("mousemove", (e) => onMove(e, host));
  });
  if (chartsArea) chartsArea.addEventListener("mouseleave", onLeave);
}

function route() {
  const p = window.location.pathname.replace(/\/+$/, "") || "/";
  if (p === "/" || p === "/index.html") return "home";
  return p.replace(/^\//, "");
}

function setStatus(ok) {
  const dot = document.getElementById("dot-esi");
  const text = document.getElementById("text-esi");
  if (!dot) return;
  dot.classList.toggle("ok", ok);
  dot.classList.toggle("err", !ok);
  text.textContent = ok ? "API ready" : "API offline";
}

function renderNav() {
  const nav = document.getElementById("top-nav");
  if (!nav || !meta?.tools) return;
  const cur = "/" + (route() === "home" ? "" : route());
  nav.innerHTML = meta.tools
    .map((t) => {
      const active = cur === t.path || cur === t.path + "/" ? " active" : "";
      return `<a class="nav-btn${active}" href="${t.path}">${t.label}</a>`;
    })
    .join("");
}

async function loadMeta() {
  meta = await api("/meta");
  document.getElementById("hub-name").textContent =
    meta.wompstar?.name || "WOMPSTAR";
  document.getElementById("hub-meta").textContent = meta.wompstar?.structure_id
    ? `Structure ${meta.wompstar.structure_id}`
    : "Configure MARKET_WOMPSTAR_STRUCTURE_ID";
  const bb = document.getElementById("link-buyback");
  if (bb && meta.buyback_url) {
    bb.href = meta.buyback_url;
    bb.target = "_blank";
    bb.rel = "noopener";
  }
  renderNav();
  setStatus(true);
}

function pageHome(panel) {
  panel.innerHTML = `
    <div class="welcome-msg">
      <h1>Market tools</h1>
      <p>Dark-mode market suite for <strong>${meta?.wompstar?.name || "WOMPSTAR"}</strong>,
      inspired by <a href="https://www.adam4eve.eu/margin_finder.php" target="_blank" rel="noopener">Adam4EVE</a>
      and <a href="https://isk.gg/market-browser" target="_blank" rel="noopener">isk.gg</a>.
      Prices are cached from ESI with rate limits; configure import regions in settings (coming soon).</p>
      <div class="tool-grid" id="tool-grid"></div>
      <div class="buyback-cta">
        <strong>Corp buyback</strong> — paste your loot list on our internal calculator.
        <a href="${meta?.buyback_url || "#"}" target="_blank" rel="noopener">Open buyback →</a>
      </div>
    </div>`;
  const grid = panel.querySelector("#tool-grid");
  (meta?.tools || []).forEach((t) => {
    grid.innerHTML += `<a class="tool-card" href="${t.path}"><strong>${t.label}</strong><span style="color:var(--text-dim)">${t.path}</span></a>`;
  });
}

function columnSortKey(col) {
  if (col.sortKey === false) return null;
  return col.sortKey || col.key || null;
}

function tableHtml(columns, rows, sortState = null) {
  const colgroup = columns
    .map((c) => `<col class="${c.col || c.class || ""}"/>`)
    .join("");
  const th = columns
    .map((c) => {
      const cls = [c.col, c.class].filter(Boolean).join(" ");
      const sk = columnSortKey(c);
      if (sk && sortState) {
        const active = sortState.sortKey === sk;
        const arrow = active ? (sortState.sortDir === "asc" ? " ▲" : " ▼") : "";
        return `<th class="${cls} th-sortable" data-sort-key="${escapeAttr(sk)}" scope="col" tabindex="0" aria-sort="${active ? (sortState.sortDir === "asc" ? "ascending" : "descending") : "none"}">${escapeHtml(c.label)}<span class="sort-indicator" aria-hidden="true">${arrow}</span></th>`;
      }
      return `<th class="${cls}" scope="col">${escapeHtml(c.label)}</th>`;
    })
    .join("");
  const tb = rows
    .map((row) => {
      const tds = columns
        .map((c) => {
          const v = c.render ? c.render(row) : row[c.key];
          const cls = [c.col, c.class].filter(Boolean).join(" ");
          return `<td class="${cls}">${v ?? ""}</td>`;
        })
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="data"><colgroup>${colgroup}</colgroup><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table></div>`;
}

function mountSortableTable(container, columns, rows, options = {}) {
  let data = rows;
  let sortKey =
    options.defaultSortKey ??
    columns.find((c) => c.defaultSort)?.sortKey ??
    columnSortKey(columns.find((c) => columnSortKey(c))) ??
    null;
  let sortDir = options.defaultSortDir ?? "desc";

  function colForKey(key) {
    return columns.find((c) => columnSortKey(c) === key);
  }

  function rowSortValue(row, col) {
    if (col.sortValue) return col.sortValue(row);
    const k = columnSortKey(col);
    return k ? row[k] : null;
  }

  function compareRows(a, b, col) {
    let va = rowSortValue(a, col);
    let vb = rowSortValue(b, col);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string" || typeof vb === "string") {
      return String(va).localeCompare(String(vb), undefined, { sensitivity: "base" });
    }
    return Number(va) - Number(vb);
  }

  function sortedRows() {
    const col = colForKey(sortKey);
    if (!col) return data;
    const mul = sortDir === "asc" ? 1 : -1;
    return [...data].sort((a, b) => compareRows(a, b, col) * mul);
  }

  function onHeaderClick(key) {
    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = colForKey(key)?.defaultSortDir || "asc";
    }
    paint();
  }

  function bindHeaders() {
    container.querySelectorAll("th.th-sortable[data-sort-key]").forEach((th) => {
      const key = th.dataset.sortKey;
      th.addEventListener("click", () => onHeaderClick(key));
      th.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onHeaderClick(key);
        }
      });
    });
  }

  function paint() {
    container.innerHTML = tableHtml(columns, sortedRows(), { sortKey, sortDir });
    bindHeaders();
  }

  paint();
  return {
    setRows(next) {
      data = next;
      paint();
    },
  };
}

async function pageMarginFinder(panel) {
  panel.innerHTML = `<h2 style="margin:0 0 12px;font-size:var(--sz-title)">Margin finder</h2>
    <p style="color:var(--text-dim);margin:0 0 12px">Buy/sell spread at ${meta?.wompstar?.name} with Jita and Amarr reference prices.</p>
    <div class="filter-bar">
      <div class="filter-bar-row">
        <label>Min trades <input type="number" id="mf-trades" value="1" min="0" style="width:64px"/></label>
        <label>Min ISK vol. <input type="number" id="mf-isk" value="0" min="0" style="width:120px"/></label>
        <button class="nav-btn" id="mf-refresh">Refresh</button>
      </div>
    </div>
    <div id="mf-table"><div class="loading-msg">Loading spreads…</div></div>`;

  async function load() {
    const minTrades = document.getElementById("mf-trades").value;
    const minIsk = document.getElementById("mf-isk").value;
    const data = await api(
      `/margin/finder?min_trades=${minTrades}&min_isk_volume=${minIsk}&limit=150`
    );
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 32),
      },
      {
        label: "Item",
        col: "col-item",
        sortKey: "type_name",
        sortValue: (r) => (r.type_name || `Type ${r.type_id}`).toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => {
          const name = r.type_name || `Type ${r.type_id}`;
          const q = encodeURIComponent(name);
          return `<a href="/market-browser?name=${q}">${escapeHtml(name)}</a>`;
        },
      },
      {
        label: "Spread (ISK)",
        sortKey: "spread_isk",
        sortValue: (r) => Number(r.spread_isk ?? r.spread ?? 0),
        defaultSort: true,
        defaultSortDir: "desc",
        class: "num",
        render: (r) => fmtIsk(r.spread_isk ?? r.spread),
      },
      {
        label: "Spread %",
        sortKey: "spread_pct",
        class: "num",
        defaultSortDir: "desc",
        render: (r) => (r.spread_pct != null ? `${r.spread_pct}%` : "—"),
      },
      {
        label: "Buy",
        sortKey: "buy_price",
        class: "num buy",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.buy_price),
      },
      {
        label: "Sell",
        sortKey: "sell_price",
        class: "num sell",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.sell_price),
      },
      ...hubPriceColumns(false),
    ];
    const el = document.getElementById("mf-table");
    if (!data.rows?.length) {
      el.innerHTML =
        '<p class="loading-msg">No spreads yet. Ensure structure sync is configured.</p>';
      return;
    }
    mountSortableTable(el, cols, data.rows, {
      defaultSortKey: "spread_isk",
      defaultSortDir: "desc",
    });
  }

  document.getElementById("mf-refresh").addEventListener("click", load);
  await load();
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

async function pageMarketBrowser(panel) {
  const params = new URLSearchParams(window.location.search);
  const initialName = params.get("name") || "";
  const initialType = params.get("type");

  panel.innerHTML = `
    <h2 style="margin:0 0 12px">Market browser</h2>
    <p style="color:var(--text-dim);margin:0 0 12px;font-size:var(--sz-label)">
      Full EVE market catalog. Prices shown for ${meta?.wompstar?.name || "WOMPSTAR"} when listed.
    </p>
    <div class="mb-layout">
      <aside class="mb-sidebar" id="mb-sidebar">
        <div class="mb-sidebar-toolbar">
          <span class="mb-total-label" id="mb-total-label">Loading…</span>
          <label class="mb-filter-listed">
            <input type="checkbox" id="mb-listed-only"/>
            <span>With orders at hub only</span>
          </label>
          <div class="search-wrap">
            <input type="search" id="mb-sidebar-search" placeholder="Filter groups…" autocomplete="off" spellcheck="false"/>
          </div>
        </div>
        <div class="mb-sidebar-tree" id="mb-sidebar-tree">
          <div class="loading-msg">Loading market groups…</div>
        </div>
      </aside>
      <div class="mb-main">
        <div class="mb-header">
          <div class="search-wrap">
            <input type="search" id="mb-search" placeholder="Search item name…" autocomplete="off" spellcheck="false"/>
            <div class="search-suggestions hidden" id="mb-suggest"></div>
          </div>
        </div>
        <div id="mb-body"><div class="loading-msg">Select an item from the list or search.</div></div>
      </div>
    </div>`;

  const searchEl = document.getElementById("mb-search");
  const sidebarSearchEl = document.getElementById("mb-sidebar-search");
  const listedOnlyEl = document.getElementById("mb-listed-only");
  const suggestEl = document.getElementById("mb-suggest");
  const sidebarTreeEl = document.getElementById("mb-sidebar-tree");
  const totalLabelEl = document.getElementById("mb-total-label");
  const bodyEl = document.getElementById("mb-body");

  let catalog = [];
  let fullTree = [];
  let treeTotal = 0;
  let listedTotal = 0;
  let catalogLoaded = false;
  let catalogSyncRunning = false;
  let catalogPollTimer = null;
  let activeTypeId = null;
  let suggestFocus = -1;

  function listedOnly() {
    return listedOnlyEl?.checked ?? false;
  }

  function setUrl(typeId, name) {
    const q = encodeURIComponent(name);
    history.replaceState(null, "", `/market-browser?name=${q}&type=${typeId}`);
  }

  function filterTree(nodes, needle) {
    if (!needle) return nodes;
    const out = [];
    for (const node of nodes) {
      if (node.kind === "type") {
        if (node.name.toLowerCase().includes(needle)) out.push(node);
        continue;
      }
      const nameHit = (node.name || "").toLowerCase().includes(needle);
      const kids = filterTree(node.children || [], needle);
      if (nameHit || kids.length) {
        out.push({ ...node, children: nameHit ? node.children || [] : kids });
      }
    }
    return out;
  }

  function renderTypeBtn(t) {
    const active = t.type_id === activeTypeId ? "active" : "";
    const dim = t.listed === false ? " unlisted" : "";
    return `<li><button type="button" class="type-link${dim} ${active}" data-tid="${t.type_id}" data-name="${escapeAttr(t.name)}">
      ${typeIconImg(t.type_id, 20)}
      <span>${escapeHtml(t.name)}</span>
    </button></li>`;
  }

  function groupCountLabel(node) {
    const total = node.count ?? 0;
    const listed = node.listed_count ?? 0;
    if (listedOnly() && listed > 0) {
      return ` <span class="mb-grp-count">(${listed.toLocaleString()})</span>`;
    }
    if (listed > 0 && listed < total) {
      return ` <span class="mb-grp-count">(${listed.toLocaleString()} / ${total.toLocaleString()})</span>`;
    }
    if (total > 0) {
      return ` <span class="mb-grp-count">(${total.toLocaleString()})</span>`;
    }
    return "";
  }

  function renderTreeNodes(nodes, expandAll = false) {
    return nodes
      .map((node) => {
        if (node.kind === "type") return renderTypeBtn(node);
        const kids = node.children || [];
        const cnt = groupCountLabel(node);
        const open = expandAll ? " open" : "";
        const hasKids = kids.length > 0;
        const directCount = listedOnly()
          ? (node.direct_listed_count ?? 0)
          : (node.direct_count ?? 0);
        const typesSlot = directCount
          ? `<ul class="mb-cat-tree mb-types-slot" data-group-id="${node.group_id}"></ul>`
          : "";
        const childTree = hasKids
          ? `<ul class="mb-cat-tree">${renderTreeNodes(kids, expandAll)}</ul>${typesSlot}`
          : typesSlot;
        if (!hasKids && !directCount) return "";
        return `<li><details class="mb-cat" data-group-id="${node.group_id}"${open}><summary>${escapeHtml(node.name)}${cnt}</summary>${childTree}</details></li>`;
      })
      .join("");
  }

  async function loadGroupTypes(detailsEl) {
    const gid = detailsEl.dataset.groupId;
    if (!gid || detailsEl.dataset.typesLoaded === "1") return;
    let slot = detailsEl.querySelector(".mb-types-slot");
    if (!slot) {
      slot = document.createElement("ul");
      slot.className = "mb-cat-tree mb-types-slot";
      slot.dataset.groupId = gid;
      detailsEl.appendChild(slot);
    }
    slot.innerHTML = '<li class="loading-msg" style="padding:6px 10px">Loading items…</li>';
    try {
      const data = await api(
        `/browser/group/${gid}/types?listed_only=${listedOnly() ? "true" : "false"}`
      );
      const types = data.types || [];
      slot.innerHTML = types.length
        ? types.map((t) => renderTypeBtn(t)).join("")
        : '<li class="loading-msg" style="padding:6px 10px">No items</li>';
      bindTypeButtons(slot);
      detailsEl.dataset.typesLoaded = "1";
    } catch (e) {
      slot.innerHTML = `<li class="loading-msg">${escapeHtml(e.message)}</li>`;
    }
  }

  function bindTypeButtons(root) {
    root.querySelectorAll("button.type-link[data-tid]").forEach((btn) => {
      btn.addEventListener("click", () =>
        selectItem(Number(btn.dataset.tid), btn.dataset.name)
      );
    });
  }

  function updateTotalLabel() {
    const hub = meta?.wompstar?.name || "hub";
    if (catalogSyncRunning) {
      totalLabelEl.textContent = "Importing catalog from EVE Ref…";
      return;
    }
    if (!catalogLoaded) {
      totalLabelEl.textContent =
        "Catalog not loaded — syncing automatically or run POST /api/market/v1/sync/groups";
      return;
    }
    if (listedOnly()) {
      totalLabelEl.textContent = `${listedTotal.toLocaleString()} types with orders at ${hub}`;
    } else {
      totalLabelEl.textContent = `${treeTotal.toLocaleString()} market types · ${listedTotal.toLocaleString()} listed at ${hub}`;
    }
  }

  function scheduleCatalogPoll() {
    if (catalogPollTimer) clearInterval(catalogPollTimer);
    if (!catalogSyncRunning && catalogLoaded) return;
    catalogPollTimer = setInterval(() => {
      loadTree().catch(() => {});
      api("/sync/catalog")
        .then((s) => {
          if (!s.running && s.loaded) {
            clearInterval(catalogPollTimer);
            catalogPollTimer = null;
          }
        })
        .catch(() => {});
    }, 8000);
  }

  function renderSidebar(filter = "") {
    const needle = filter.trim().toLowerCase();
    if (!fullTree.length && !needle) {
      const hub = meta?.wompstar?.name || "WOMPSTAR";
      if (listedOnly()) {
        sidebarTreeEl.innerHTML =
          listedTotal > 0
            ? `<div class="loading-msg">Linking ${listedTotal.toLocaleString()} listed types to market groups… try refresh, or run <code>POST /api/market/v1/sync/hub-groups</code>.</div>`
            : `<div class="loading-msg">No orders at ${escapeHtml(hub)} yet. Run <code>POST /api/market/v1/sync/structure</code>.</div>`;
      } else if (!catalogLoaded) {
        sidebarTreeEl.innerHTML =
          '<div class="loading-msg">Full catalog not imported yet. Run <code>POST /api/market/v1/sync/groups</code> (EVE Ref groups + types, ~10 min).</div>';
      } else {
        sidebarTreeEl.innerHTML =
          '<div class="loading-msg">No matching categories.</div>';
      }
      return;
    }
    const tree = filterTree(fullTree, needle);
    if (!tree.length) {
      sidebarTreeEl.innerHTML = needle
        ? '<div class="loading-msg">No matching groups or items.</div>'
        : '<div class="loading-msg">No market groups loaded.</div>';
      return;
    }
    sidebarTreeEl.innerHTML = `<ul class="mb-cat-tree">${renderTreeNodes(tree, !!needle)}</ul>`;
    bindTypeButtons(sidebarTreeEl);
    sidebarTreeEl.querySelectorAll("details.mb-cat[data-group-id]").forEach((det) => {
      det.addEventListener("toggle", () => {
        if (det.open) loadGroupTypes(det);
      });
      if (det.open) loadGroupTypes(det);
    });
  }

  async function loadTree() {
    const listed = listedOnly();
    let data;
    try {
      data = await api(`/browser/tree?listed_only=${listed}`);
    } catch (e) {
      if (!String(e.message).startsWith("404 ")) throw e;
      const legacy = await api("/browser/categories");
      data = {
        children: legacy.children || legacy.tree || [],
        total_types: legacy.total_types ?? legacy.count ?? 0,
        listed_types: legacy.count ?? 0,
        catalog_loaded: true,
      };
    }
    fullTree = data.children || data.tree || [];
    treeTotal = data.total_types ?? 0;
    listedTotal = data.listed_types ?? 0;
    catalogLoaded = Boolean(data.catalog_loaded);
    catalogSyncRunning = Boolean(data.catalog_sync_running);
    updateTotalLabel();
    renderSidebar(sidebarSearchEl.value);
    scheduleCatalogPoll();
    if (listedOnly() && listedTotal > 0 && !fullTree.length) {
      api("/sync/hub-groups", { method: "POST" })
        .then(() => loadTree())
        .catch(() => {});
    }
  }

  async function loadItem(typeId, name) {
    bodyEl.innerHTML = '<div class="loading-msg">Loading orders…</div>';
    activeTypeId = typeId;
    searchEl.value = name;
    hideSuggestions();
    renderSidebar(sidebarSearchEl.value);

    let data;
    try {
      data = await api(`/browser/item/${typeId}`);
    } catch {
      const q = encodeURIComponent(name);
      data = await api(`/browser/item?name=${q}&type_id=${typeId}`);
    }

    const displayName = data.type_name || name;
    setUrl(typeId, displayName);

    const oc = data.order_counts || {};
    const sellN = oc.sell ?? (data.sell_orders || []).length;
    const buyN = oc.buy ?? (data.buy_orders || []).length;
    const hub = meta?.wompstar?.name || "WOMPSTAR";

    const sellCols = [
      { label: "Price", render: (o) => fmtIsk(o.price), class: "num sell" },
      { label: "Vol", key: "volume_remain", class: "num" },
      { label: "Min", key: "min_volume", class: "num" },
    ];
    const buyCols = [
      { label: "Price", render: (o) => fmtIsk(o.price), class: "num buy" },
      { label: "Vol", key: "volume_remain", class: "num" },
      { label: "Min", key: "min_volume", class: "num" },
    ];

    bodyEl.innerHTML = `
      <h3 class="mb-item-title">
        ${typeIconImg(typeId, 64)}
        <span>${escapeHtml(displayName)}</span>
      </h3>
      <p class="mb-subtitle">${escapeHtml(hub)} — <strong>${sellN}</strong> sell / <strong>${buyN}</strong> buy orders (live structure market)</p>
      <div class="mb-orders-grid">
        <div class="mb-orders-panel">
          <h4 class="sell">Sell orders</h4>
          ${tableHtml(sellCols, data.sell_orders || [])}
        </div>
        <div class="mb-orders-panel">
          <h4 class="buy">Buy orders</h4>
          ${tableHtml(buyCols, data.buy_orders || [])}
        </div>
      </div>
      <section class="mb-history" id="mb-history">
        <h4>Price &amp; volume history</h4>
        <p class="mb-history-note">${escapeHtml(data.history?.note || "")}</p>
        <div class="hist-tabs">
          <button type="button" class="nav-btn hist-tab active" data-days="30">30 days</button>
          <button type="button" class="nav-btn hist-tab" data-days="60">60 days</button>
          <button type="button" class="nav-btn hist-tab" data-days="180">6 months</button>
        </div>
        <div class="mb-charts-area">
        <div class="chart-legend-row">
          ${chartLegendItem("#e85d5d", "High", "sell")}
          ${chartLegendItem("#6eb5ff", "Average")}
          ${chartLegendItem("#4dbb6a", "Low", "buy")}
        </div>
        <div class="chart-host chart-host-price">
          <canvas id="mb-chart-price" class="mb-chart" height="180"></canvas>
        </div>
        <h4 class="chart-section-title">Volume</h4>
        <div class="chart-legend-row">
          ${chartLegendItem("#4a5568", "Units traded", "vol")}
          <span class="chart-legend-hint">Hover charts for exact values</span>
        </div>
        <div class="chart-host chart-host-vol">
          <canvas id="mb-chart-vol" class="mb-chart" height="120"></canvas>
        </div>
        </div>
        <div id="mb-chart-tooltip" class="chart-tooltip hidden" role="tooltip"></div>
      </section>`;

    const histWrap = document.getElementById("mb-history");
    const histDays = data.history?.days || [];
    let period = 30;
    const paint = () => {
      const hi = histWrap._chartState?.hoverIndex ?? -1;
      const st = drawHistoryCharts(histWrap, histDays, period, hi);
      histWrap._chartState = { days: histDays, period, layout: st?.layout, hoverIndex: hi };
    };
    histWrap._chartHoverBound = false;
    paint();
    bindHistoryChartHover(histWrap);
    if (!histWrap._resizeBound) {
      histWrap._resizeBound = true;
      window.addEventListener("resize", paint);
    }
    histWrap.querySelectorAll(".hist-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        histWrap.querySelectorAll(".hist-tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        period = Number(btn.dataset.days);
        if (histWrap._chartState) histWrap._chartState.hoverIndex = -1;
        paint();
      });
    });
  }

  function selectItem(typeId, name) {
    loadItem(typeId, name).catch((e) => {
      bodyEl.innerHTML = `<p class="loading-msg">Failed to load item: ${escapeHtml(e.message)}</p>`;
    });
  }

  function hideSuggestions() {
    suggestEl.classList.add("hidden");
    suggestEl.innerHTML = "";
    suggestFocus = -1;
  }

  function showSuggestions(matches) {
    if (!matches.length) {
      suggestEl.innerHTML = '<div class="hint">No matching listed items</div>';
      suggestEl.classList.remove("hidden");
      return;
    }
    suggestEl.innerHTML = matches
      .map((t, i) => {
        const sell = t.best_sell != null ? fmtIsk(t.best_sell) : "";
        return `<button type="button" data-idx="${i}" data-tid="${t.type_id}" data-name="${escapeAttr(t.name)}">
          ${typeIconImg(t.type_id, 24)}
          <span>${escapeHtml(t.name)}</span>
          ${sell ? `<span class="mb-price sell">${sell}</span>` : ""}
        </button>`;
      })
      .join("");
    suggestEl.classList.remove("hidden");
    suggestEl.querySelectorAll("button[data-tid]").forEach((btn) => {
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        selectItem(Number(btn.dataset.tid), btn.dataset.name);
      });
    });
  }

  const fetchSuggestions = debounce(async () => {
    const q = searchEl.value.trim();
    if (q.length < 1) {
      hideSuggestions();
      return;
    }
    try {
      const { types } = await api(
        `/browser/search?q=${encodeURIComponent(q)}&limit=25&listed_only=${listedOnly()}`
      );
      showSuggestions(types);
    } catch {
      hideSuggestions();
    }
  }, 180);

  searchEl.addEventListener("input", fetchSuggestions);
  sidebarSearchEl.addEventListener("input", () => renderSidebar(sidebarSearchEl.value));
  listedOnlyEl.addEventListener("change", () => {
    sidebarTreeEl.querySelectorAll("details.mb-cat").forEach((d) => {
      delete d.dataset.typesLoaded;
    });
    loadTree().catch((e) => {
      sidebarTreeEl.innerHTML = `<div class="loading-msg">${escapeHtml(e.message)}</div>`;
    });
  });
  searchEl.addEventListener("focus", () => {
    if (searchEl.value.trim()) fetchSuggestions();
  });
  searchEl.addEventListener("keydown", (e) => {
    const buttons = [...suggestEl.querySelectorAll("button[data-tid]")];
    if (e.key === "ArrowDown") {
      e.preventDefault();
      suggestFocus = Math.min(suggestFocus + 1, buttons.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      suggestFocus = Math.max(suggestFocus - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (suggestFocus >= 0 && buttons[suggestFocus]) {
        const b = buttons[suggestFocus];
        selectItem(Number(b.dataset.tid), b.dataset.name);
        return;
      }
      const q = searchEl.value.trim().toLowerCase();
      const hit =
        catalog.find((t) => t.name.toLowerCase() === q) ||
        catalog.find((t) => t.name.toLowerCase().includes(q));
      if (hit) selectItem(hit.type_id, hit.name);
      return;
    } else if (e.key === "Escape") {
      hideSuggestions();
      return;
    } else {
      return;
    }
    buttons.forEach((b, i) => b.classList.toggle("focused", i === suggestFocus));
    if (buttons[suggestFocus]) buttons[suggestFocus].scrollIntoView({ block: "nearest" });
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) hideSuggestions();
  });

  try {
    const cat = await api("/browser/catalog");
    catalog = cat.types || [];
    await loadTree();
    if (initialName) {
      searchEl.value = initialName;
      const q = initialName.trim().toLowerCase();
      const hit =
        catalog.find((t) => t.name.toLowerCase() === q) ||
        catalog.find((t) => t.name.toLowerCase().includes(q));
      if (hit) await loadItem(hit.type_id, hit.name);
      else {
        const { types } = await api(`/browser/search?q=${encodeURIComponent(initialName)}&limit=1`);
        if (types[0]) await loadItem(types[0].type_id, types[0].name);
      }
    } else if (initialType) {
      const tid = Number(initialType);
      const hit = catalog.find((t) => t.type_id === tid);
      if (hit) await loadItem(hit.type_id, hit.name);
      else await loadItem(tid, `Type ${tid}`);
    } else {
      bodyEl.innerHTML =
        '<div class="loading-msg">Expand a category or search for an item. Enable “With orders at hub only” to hide unlisted types.</div>';
    }
  } catch (e) {
    totalLabelEl.textContent = "Failed to load";
    sidebarTreeEl.innerHTML = `<div class="loading-msg">${escapeHtml(e.message)}</div>`;
  }
}

function pageStub(panel, title, blurb) {
  panel.innerHTML = `
    <h2 style="margin:0 0 8px">${title}</h2>
    <p style="color:var(--text-dim)">${blurb}</p>
    <div class="coming-soon-box">
      ${syncStatusHtml()}
      <p style="margin:8px 0 0">This view is not built yet. Use
        <a href="/margin_finder">Margin finder</a> or
        <a href="/market-browser">Market browser</a> for live WOMPSTAR data.</p>
    </div>`;
}

async function pageMarketTrends(panel) {
  panel.innerHTML = `<h2 style="margin:0 0 8px">Market trends</h2>
    <p style="color:var(--text-dim)">Top spreads at ${meta?.wompstar?.name} with Jita / Amarr / hub sell &amp; buy on chart and table.</p>
    <div id="mt-charts"></div>
    <div id="mt-table"><div class="loading-msg">Loading…</div></div>`;
  const chartsEl = document.getElementById("mt-charts");
  const tableEl = document.getElementById("mt-table");
  try {
    const data = await api("/margin/finder?limit=80");
    if (data.rows?.length) mountHubCompareCharts(chartsEl, data.rows);
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 28),
      },
      {
        label: "Item",
        col: "col-item",
        sortKey: "type_name",
        sortValue: (r) => (r.type_name || `Type ${r.type_id}`).toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => {
          const n = r.type_name || `Type ${r.type_id}`;
          return `<a href="/market-browser?name=${encodeURIComponent(n)}">${escapeHtml(n)}</a>`;
        },
      },
      {
        label: "Spread (ISK)",
        sortKey: "spread_isk",
        sortValue: (r) => Number(r.spread_isk ?? 0),
        defaultSort: true,
        defaultSortDir: "desc",
        class: "num",
        render: (r) => fmtIsk(r.spread_isk),
      },
      {
        label: "Spread %",
        sortKey: "spread_pct",
        defaultSortDir: "desc",
        class: "num",
        render: (r) => (r.spread_pct != null ? `${r.spread_pct}%` : "—"),
      },
      ...hubPriceColumns(),
    ];
    if (!data.rows?.length) {
      tableEl.innerHTML = '<p class="loading-msg">No data.</p>';
      return;
    }
    mountSortableTable(tableEl, cols, data.rows, {
      defaultSortKey: "spread_isk",
      defaultSortDir: "desc",
    });
  } catch (e) {
    tableEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
  }
}

async function pagePriceCompare(panel) {
  const hub = meta?.wompstar?.name || "WOMPSTAR";
  const importLabel = meta?.import?.station_id
    ? "Jita 4-4 (The Forge)"
    : "Import hub";
  panel.innerHTML = `<h2 style="margin:0 0 8px">Price compare</h2>
    <p style="color:var(--text-dim);margin:0 0 12px;font-size:var(--sz-label)">
      <span id="pc-subtitle">Loading ${escapeHtml(hub)} vs ${escapeHtml(importLabel)}…</span>
    </p>
    <div id="pc-table"><div class="loading-msg">Loading…</div></div>`;
  const subtitleEl = document.getElementById("pc-subtitle");
  const tableEl = document.getElementById("pc-table");

  function itemLabel(r) {
    return r.name || r.type_name || `Type ${r.type_id}`;
  }

  function renderTable(rows, label, janiceUsed) {
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 28),
      },
      {
        label: "Item",
        col: "col-item",
        sortKey: "name",
        sortValue: (r) => itemLabel(r).toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => {
          const n = itemLabel(r);
          return `<a href="/market-browser?name=${encodeURIComponent(n)}">${escapeHtml(n)}</a>`;
        },
      },
      {
        label: `${hub} sell`,
        sortKey: "best_sell",
        class: "num sell",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.best_sell),
      },
      {
        label: `${hub} buy`,
        sortKey: "best_buy",
        class: "num buy",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.best_buy),
      },
      {
        label: "Jita sell",
        sortKey: "jita_sell",
        class: "num sell",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.jita_sell),
      },
      {
        label: "Jita buy",
        sortKey: "jita_buy",
        class: "num buy",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.jita_buy),
      },
      {
        label: "Amarr sell",
        sortKey: "amarr_sell",
        class: "num sell",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.amarr_sell),
      },
      {
        label: "Amarr buy",
        sortKey: "amarr_buy",
        class: "num buy",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.amarr_buy),
      },
    ];
    if (!rows.length) {
      tableEl.innerHTML =
        '<p class="loading-msg">No listed items yet. Run structure sync.</p>';
    } else {
      mountSortableTable(tableEl, cols, rows, {
        defaultSortKey: "name",
        defaultSortDir: "asc",
      });
    }
    if (subtitleEl) {
      const src = janiceUsed ? "Janice appraisal prices" : "ESI region orders";
      subtitleEl.textContent = `${rows.length.toLocaleString()} items — ${hub} vs ${label} (${src})`;
    }
  }

  try {
    const data = await api("/compare?limit=500");
    const label = data.import_label || importLabel;
    renderTable(data.types || [], label, data.janice_used);
    if (data.jita_pending) {
      tableEl.insertAdjacentHTML(
        "beforeend",
        '<p class="loading-msg" style="padding:12px 0 0">Jita prices syncing from ESI — refresh in a minute.</p>'
      );
      window.setTimeout(async () => {
        try {
          const again = await api("/compare?limit=500");
          if (!(again.jita_pending && again.types?.some((t) => t.jita_sell == null && t.jita_buy == null))) {
            renderTable(again.types || [], again.import_label || label, again.janice_used);
          }
        } catch {
          /* ignore poll errors */
        }
      }, 45000);
    }
  } catch (e) {
    tableEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
  }
}

async function pageContractPrices(panel) {
  const hub = meta?.wompstar?.name || "WOMPSTAR";
  const corps = (meta?.contracts?.issuer_corp_ids || []).join(", ") || "not configured";
  panel.innerHTML = `<h2 style="margin:0 0 8px">Contract prices</h2>
    <p style="color:var(--text-dim);margin:0 0 12px">
      Outstanding corp item-exchange contracts (issuer corps: <code>${escapeHtml(corps)}</code>).
      Margins vs contract unit price if you sell on ${escapeHtml(hub)} market or fulfill the contract.
    </p>
    <div class="filter-bar">
      <button class="nav-btn" id="cp-sync">Sync contracts</button>
      <span id="cp-status" style="color:var(--text-dim);font-size:var(--sz-label)"></span>
    </div>
    <div id="cp-table"><div class="loading-msg">Loading…</div></div>`;
  const tableEl = document.getElementById("cp-table");
  const statusEl = document.getElementById("cp-status");

  async function load() {
    const data = await api("/contracts/margins?limit=500");
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 28),
      },
      {
        label: "Item",
        col: "col-item",
        sortKey: "type_name",
        sortValue: (r) => (r.type_name || "").toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => escapeHtml(r.type_name || `Type ${r.type_id}`),
      },
      {
        label: "Contract ISK/u",
        sortKey: "contract_unit_isk",
        class: "num",
        defaultSort: true,
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.contract_unit_isk),
      },
      { label: "Qty", sortKey: "quantity", class: "num", render: (r) => fmtVol(r.quantity) },
      { label: "Jita sell", sortKey: "jita_sell", class: "num sell", render: (r) => fmtIsk(r.jita_sell) },
      { label: "Amarr sell", sortKey: "amarr_sell", class: "num sell", render: (r) => fmtIsk(r.amarr_sell) },
      {
        label: `${hub} sell`,
        sortKey: "wompstar_sell",
        class: "num sell",
        render: (r) => fmtIsk(r.wompstar_sell),
      },
      {
        label: "Δ vs WOMP sell",
        sortKey: "margin_vs_wompstar",
        class: "num",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.margin_vs_wompstar),
      },
      {
        label: "Δ vs Jita sell",
        sortKey: "margin_vs_jita",
        class: "num",
        render: (r) => fmtIsk(r.margin_vs_jita),
      },
      {
        label: "Δ vs Amarr sell",
        sortKey: "margin_vs_amarr",
        class: "num",
        render: (r) => fmtIsk(r.margin_vs_amarr),
      },
      {
        label: "% vs WOMP",
        sortKey: "pct_vs_wompstar",
        class: "num",
        render: (r) => (r.pct_vs_wompstar != null ? `${r.pct_vs_wompstar}%` : "—"),
      },
      {
        label: "Contract",
        sortKey: "contract_id",
        render: (r) =>
          `<span class="dim">#${r.contract_id}</span> ${escapeHtml((r.contract_title || "").slice(0, 40))}`,
      },
    ];
    if (!data.rows?.length) {
      tableEl.innerHTML =
        '<p class="loading-msg">No active contracts cached. Set MARKET_WOMP_CONTRACT_ISSUER_CORP_ID(S) and click Sync.</p>';
      return;
    }
    mountSortableTable(tableEl, cols, data.rows, {
      defaultSortKey: "margin_vs_wompstar",
      defaultSortDir: "desc",
    });
  }

  document.getElementById("cp-sync").addEventListener("click", async () => {
    statusEl.textContent = "Syncing…";
    try {
      await api("/sync/contracts", { method: "POST" });
      statusEl.textContent = "Background sync started — refresh in ~1 min.";
      window.setTimeout(() => load().catch(() => {}), 60000);
    } catch (e) {
      statusEl.textContent = e.message;
    }
  });

  try {
    await load();
  } catch (e) {
    tableEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
  }
}

function drawPiBarChart(canvas, rows, valueKey, labelKey = "name") {
  const slice = rows.slice(0, 14);
  if (!slice.length || !canvas) return;
  const vals = slice.map((r) => Number(r[valueKey] ?? 0));
  const labels = slice.map((r) => String(r[labelKey] || "").slice(0, 16));
  const pad = 44;
  const ch = 200;
  const ctx = canvas.getContext("2d");
  const dpr = devicePixelRatio;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = ch * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cw = canvas.clientWidth;
  ctx.clearRect(0, 0, cw, ch);
  const max = Math.max(...vals.map(Math.abs), 1);
  const groupW = (cw - pad * 2) / Math.max(slice.length, 1);
  const barW = Math.max(4, groupW * 0.65);
  slice.forEach((row, i) => {
    const v = Number(row[valueKey] ?? 0);
    const gx = pad + i * groupW + groupW * 0.15;
    const bh = (Math.abs(v) / max) * (ch - pad - 20);
    const y = v >= 0 ? ch - pad - bh : ch - pad;
    ctx.fillStyle = v >= 0 ? "#4dbb6a" : "#e85d5d";
    ctx.fillRect(gx, y, barW, bh);
    ctx.fillStyle = "#8b95a8";
    ctx.font = "9px Segoe UI, sans-serif";
    ctx.save();
    ctx.translate(gx + 4, ch - 4);
    ctx.rotate(-0.45);
    ctx.fillText(labels[i], 0, 0);
    ctx.restore();
  });
  ctx.fillStyle = "#8b95a8";
  ctx.font = "10px Segoe UI, sans-serif";
  ctx.fillText(fmtIsk(max), 4, 12);
}

function drawPiTierChart(canvas, rows) {
  const tiers = [1, 2, 3, 4];
  const best = tiers.map((t) => {
    const tierRows = rows.filter((r) => r.tier === t);
    if (!tierRows.length) return { tier: t, profit_iph: 0 };
    const top = tierRows.reduce((a, b) =>
      Number(b.profit_iph ?? 0) > Number(a.profit_iph ?? 0) ? b : a
    );
    return { tier: t, profit_iph: top.profit_iph, name: top.name };
  });
  drawPiBarChart(
    canvas,
    best.map((b) => ({ name: `P${b.tier}`, profit_iph: b.profit_iph })),
    "profit_iph",
    "name"
  );
}

function mountPiCharts(container, rows) {
  if (!rows?.length) {
    container.innerHTML = "";
    return;
  }
  const sorted = [...rows].sort(
    (a, b) => Number(b.profit_iph ?? 0) - Number(a.profit_iph ?? 0)
  );
  container.innerHTML = `
    <div class="hub-charts-wrap">
      <p class="chart-section-title">Profit ISK / hour (top commodities)</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="pi-chart-top"></canvas></div>
      <p class="chart-section-title">Best profit IPH by tier (P1–P4)</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="pi-chart-tier"></canvas></div>
    </div>`;
  const paint = () => {
    drawPiBarChart(
      container.querySelector("#pi-chart-top"),
      sorted,
      "profit_iph",
      "name"
    );
    drawPiTierChart(container.querySelector("#pi-chart-tier"), sorted);
  };
  paint();
  if (!container._piResizeBound) {
    container._piResizeBound = true;
    window.addEventListener("resize", paint);
  }
}

async function pagePiRank(panel) {
  const hubDefault = "jita";
  panel.innerHTML = `<h2 style="margin:0 0 8px">PI profitability</h2>
    <p style="color:var(--text-dim);margin:0 0 12px;font-size:var(--sz-label)">
      Factory and extract-style margins from EVE Ref schematics vs hub prices (Adam4EVE-style).
    </p>
    <div class="filter-bar">
      <div class="filter-bar-row">
        <label>Sale hub
          <select id="pi-hub">
            <option value="jita">Jita 4-4</option>
            <option value="amarr">Amarr VIII</option>
            <option value="wompstar">${escapeHtml(meta?.wompstar?.name || "WOMPSTAR")}</option>
          </select>
        </label>
        <label>Mode
          <select id="pi-mode">
            <option value="factory">Factory (buy inputs)</option>
            <option value="extract">Extract (no input cost)</option>
            <option value="both">Both</option>
          </select>
        </label>
        <label>Tier
          <select id="pi-tier">
            <option value="">All</option>
            <option value="1">P1</option>
            <option value="2">P2</option>
            <option value="3">P3</option>
            <option value="4">P4</option>
          </select>
        </label>
        <label>Buy from
          <select id="pi-buy">
            <option value="sell_orders">Sell orders</option>
            <option value="buy_orders">Buy orders</option>
          </select>
        </label>
        <label>Sell to
          <select id="pi-sell">
            <option value="sell_orders">Sell orders</option>
            <option value="buy_orders">Buy orders</option>
          </select>
        </label>
        <label>Customs %
          <input type="number" id="pi-customs" value="10" min="0" max="50" style="width:56px"/>
        </label>
        <label>Market %
          <input type="number" id="pi-market" value="7.5" min="0" max="50" style="width:56px"/>
        </label>
        <button class="nav-btn" id="pi-refresh">Refresh</button>
      </div>
    </div>
    <div id="pi-charts"></div>
    <div id="pi-table"><div class="loading-msg">Loading PI data…</div></div>`;

  const hubEl = document.getElementById("pi-hub");
  const tableEl = document.getElementById("pi-table");
  const chartsEl = document.getElementById("pi-charts");
  hubEl.value = hubDefault;

  async function load() {
    tableEl.innerHTML = '<div class="loading-msg">Loading…</div>';
    const q = new URLSearchParams({
      sale_hub: hubEl.value,
      mode: document.getElementById("pi-mode").value,
      buy_from: document.getElementById("pi-buy").value,
      sell_to: document.getElementById("pi-sell").value,
      customs_pct: document.getElementById("pi-customs").value,
      market_pct: document.getElementById("pi-market").value,
      limit: "200",
    });
    const tier = document.getElementById("pi-tier").value;
    if (tier) q.set("tier", tier);
    const data = await api(`/pi/rank?${q}`);
    const rows = data.rows || [];
    mountPiCharts(chartsEl, rows);
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 28),
      },
      {
        label: "Commodity",
        col: "col-item",
        sortKey: "name",
        sortValue: (r) => (r.name || "").toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => escapeHtml(r.name || `Type ${r.type_id}`),
      },
      { label: "Px", sortKey: "tier_label", class: "num", render: (r) => r.tier_label || "—" },
      {
        label: "Mode",
        sortKey: "mode",
        render: (r) => escapeHtml(r.mode || "factory"),
      },
      {
        label: "Profit",
        sortKey: "profit",
        class: "num",
        defaultSort: true,
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.profit),
      },
      {
        label: "P%",
        sortKey: "profit_pct",
        class: "num",
        render: (r) => (r.profit_pct != null ? `${r.profit_pct}%` : "—"),
      },
      {
        label: "ISK / h",
        sortKey: "profit_iph",
        class: "num",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.profit_iph),
      },
      {
        label: "Sell",
        sortKey: "sell_unit",
        class: "num sell",
        render: (r) => fmtIsk(r.sell_unit),
      },
      {
        label: "Mat. cost",
        sortKey: "material_cost",
        class: "num",
        render: (r) => fmtIsk(r.material_cost),
      },
    ];
    if (!rows.length) {
      tableEl.innerHTML =
        '<p class="loading-msg">No rows — run <code>POST /api/market/v1/sync/import</code> for hub prices.</p>';
      return;
    }
    mountSortableTable(tableEl, cols, rows, {
      defaultSortKey: "profit_iph",
      defaultSortDir: "desc",
    });
    if (data.prices_pending) {
      tableEl.insertAdjacentHTML(
        "beforeend",
        `<p class="loading-msg" style="padding:12px 0 0">Hub prices still syncing for ${escapeHtml(data.sale_hub_label || hubEl.value)} — refresh in a minute.</p>`
      );
    }
  }

  document.getElementById("pi-refresh").addEventListener("click", () => load().catch(showErr));
  ["pi-hub", "pi-mode", "pi-tier", "pi-buy", "pi-sell"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => load().catch(showErr));
  });

  function showErr(e) {
    tableEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
    chartsEl.innerHTML = "";
  }

  try {
    await load();
  } catch (e) {
    showErr(e);
  }
}

function drawVolumeCompareChart(canvas, rows) {
  const slice = rows.slice(0, 12);
  if (!slice.length || !canvas) return;
  const pad = 44;
  const ch = 200;
  const ctx = canvas.getContext("2d");
  const dpr = devicePixelRatio;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = ch * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cw = canvas.clientWidth;
  ctx.clearRect(0, 0, cw, ch);
  const hubVals = slice.map((r) => Number(r.hub_volume ?? 0));
  const cmpVals = slice.map((r) => Number(r.compare_volume ?? 0));
  const max = Math.max(...hubVals, ...cmpVals, 1);
  const groupW = (cw - pad * 2) / Math.max(slice.length, 1);
  const barW = Math.max(3, (groupW * 0.72) / 2);
  const hubName = meta?.wompstar?.name?.split(" ")[0] || "Hub";
  slice.forEach((row, i) => {
    const gx = pad + i * groupW + groupW * 0.12;
    const label = (row.type_name || "").slice(0, 14);
    const hv = Number(row.hub_volume ?? 0);
    const cv = Number(row.compare_volume ?? 0);
    const hb = (hv / max) * (ch - pad - 20);
    const cb = (cv / max) * (ch - pad - 20);
    ctx.fillStyle = "#4dbb6a";
    ctx.fillRect(gx, ch - pad - hb, barW, hb);
    ctx.fillStyle = "#e85d5d";
    ctx.fillRect(gx + barW + 1, ch - pad - cb, barW, cb);
    ctx.fillStyle = "#8b95a8";
    ctx.font = "9px Segoe UI, sans-serif";
    ctx.save();
    ctx.translate(gx + 4, ch - 4);
    ctx.rotate(-0.45);
    ctx.fillText(label, 0, 0);
    ctx.restore();
  });
  ctx.fillStyle = "#8b95a8";
  ctx.font = "10px Segoe UI, sans-serif";
  ctx.fillText(fmtVol(max), 4, 12);
  ctx.fillStyle = "#4dbb6a";
  ctx.fillRect(cw - pad - 100, 8, 10, 10);
  ctx.fillStyle = "#c5cdd8";
  ctx.fillText(hubName, cw - pad - 86, 17);
  ctx.fillStyle = "#e85d5d";
  ctx.fillRect(cw - pad - 48, 8, 10, 10);
  ctx.fillText("Compare", cw - pad - 34, 17);
}

function mountTradeVolCharts(container, rows, compareLabel) {
  if (!rows?.length) {
    container.innerHTML = "";
    return;
  }
  const sorted = [...rows].sort(
    (a, b) => Number(b.hub_volume ?? 0) - Number(a.hub_volume ?? 0)
  );
  container.innerHTML = `
    <div class="hub-charts-wrap">
      <p class="chart-section-title">Hub trade volume (units, top items)</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="tv-chart-hub"></canvas></div>
      <p class="chart-section-title">Hub vs ${escapeHtml(compareLabel || "compare")} volume</p>
      <div class="chart-host"><canvas class="hub-chart-canvas" id="tv-chart-compare"></canvas></div>
    </div>`;
  const paint = () => {
    drawPiBarChart(
      container.querySelector("#tv-chart-hub"),
      sorted,
      "hub_volume",
      "type_name"
    );
    drawVolumeCompareChart(
      container.querySelector("#tv-chart-compare"),
      sorted
    );
  };
  paint();
  if (!container._tvResizeBound) {
    container._tvResizeBound = true;
    window.addEventListener("resize", paint);
  }
}

async function pageTradeVolType(panel) {
  const hub = meta?.wompstar?.name || "WOMPSTAR region";
  panel.innerHTML = `<h2 style="margin:0 0 8px">Trade volume by type</h2>
    <p style="color:var(--text-dim);margin:0 0 12px;font-size:var(--sz-label)">
      Regional ESI market history — <strong>${escapeHtml(hub)}</strong> vs import hub (structure-only volume is not published by ESI).
    </p>
    <div class="filter-bar">
      <div class="filter-bar-row">
        <label>Period
          <select id="tv-days">
            <option value="7">7 days</option>
            <option value="30" selected>30 days</option>
            <option value="90">90 days</option>
            <option value="180">180 days</option>
          </select>
        </label>
        <label>Compare
          <select id="tv-compare">
            <option value="jita">Jita (The Forge)</option>
            <option value="amarr">Amarr (Domain)</option>
          </select>
        </label>
        <button class="nav-btn" id="tv-refresh">Refresh</button>
        <button class="nav-btn" id="tv-sync">Sync history</button>
      </div>
    </div>
    <p id="tv-subtitle" style="color:var(--text-dim);font-size:var(--sz-label);margin:0 0 8px"></p>
    <div id="tv-charts"></div>
    <div id="tv-table"><div class="loading-msg">Loading volumes…</div></div>`;

  const tableEl = document.getElementById("tv-table");
  const chartsEl = document.getElementById("tv-charts");
  const subtitleEl = document.getElementById("tv-subtitle");

  async function load() {
    tableEl.innerHTML = '<div class="loading-msg">Loading…</div>';
    const days = document.getElementById("tv-days").value;
    const compare = document.getElementById("tv-compare").value;
    const data = await api(`/volume/types?days=${days}&compare=${compare}&limit=500`);
    const rows = data.rows || [];
    if (subtitleEl) {
      subtitleEl.textContent = `${rows.length.toLocaleString()} types with volume — last ${data.days} days (${data.since} → today) · hub region ${data.hub_region_id} vs ${data.compare_label}`;
    }
    mountTradeVolCharts(chartsEl, rows, data.compare_label);
    const cols = [
      {
        label: "",
        col: "col-icon",
        sortKey: false,
        render: (r) => typeIconImg(r.type_id, 28),
      },
      {
        label: "Item",
        col: "col-item",
        sortKey: "type_name",
        sortValue: (r) => (r.type_name || "").toLowerCase(),
        defaultSortDir: "asc",
        render: (r) => {
          const n = r.type_name || `Type ${r.type_id}`;
          return `<a href="/market-browser?name=${encodeURIComponent(n)}">${escapeHtml(n)}</a>`;
        },
      },
      {
        label: "Hub vol.",
        sortKey: "hub_volume",
        class: "num",
        defaultSort: true,
        defaultSortDir: "desc",
        render: (r) => fmtVol(r.hub_volume),
      },
      {
        label: "Hub ISK vol.",
        sortKey: "hub_isk_volume",
        class: "num",
        defaultSortDir: "desc",
        render: (r) => fmtIsk(r.hub_isk_volume),
      },
      {
        label: "Hub avg/day",
        sortKey: "hub_avg_daily_volume",
        class: "num",
        render: (r) => fmtVol(r.hub_avg_daily_volume),
      },
      {
        label: "Compare vol.",
        sortKey: "compare_volume",
        class: "num",
        defaultSortDir: "desc",
        render: (r) => fmtVol(r.compare_volume),
      },
      {
        label: "Compare ISK vol.",
        sortKey: "compare_isk_volume",
        class: "num",
        render: (r) => fmtIsk(r.compare_isk_volume),
      },
      {
        label: "Hub / cmp",
        sortKey: "volume_ratio",
        class: "num",
        render: (r) =>
          r.volume_ratio != null ? `${(r.volume_ratio * 100).toFixed(1)}%` : "—",
      },
    ];
    if (!rows.length) {
      tableEl.innerHTML =
        '<p class="loading-msg">No cached history yet. Click <strong>Sync history</strong> (may take several minutes).</p>';
      chartsEl.innerHTML = "";
      return;
    }
    mountSortableTable(tableEl, cols, rows, {
      defaultSortKey: "hub_volume",
      defaultSortDir: "desc",
    });
    if (data.history_pending || data.history_sync_running) {
      tableEl.insertAdjacentHTML(
        "beforeend",
        '<p class="loading-msg" style="padding:12px 0 0">History sync in progress — refresh in a few minutes for more types.</p>'
      );
    }
  }

  document.getElementById("tv-refresh").addEventListener("click", () => load().catch(showErr));
  document.getElementById("tv-days").addEventListener("change", () => load().catch(showErr));
  document.getElementById("tv-compare").addEventListener("change", () => load().catch(showErr));
  document.getElementById("tv-sync").addEventListener("click", async () => {
    try {
      await api("/sync/history", { method: "POST" });
      subtitleEl.textContent = "Background history sync started…";
      window.setTimeout(() => load().catch(() => {}), 90000);
    } catch (e) {
      showErr(e);
    }
  });

  function showErr(e) {
    tableEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
    chartsEl.innerHTML = "";
  }

  try {
    await load();
  } catch (e) {
    showErr(e);
  }
}

async function pageAppraisal(panel) {
  const dest = meta?.wompstar?.name || "WOMPSTAR";
  let apMeta = { janice_configured: false, markets: [] };
  try {
    apMeta = await api("/appraisal/meta");
  } catch {
    /* use defaults */
  }

  panel.innerHTML = `
    <h2 style="margin:0 0 8px">Appraisal</h2>
    <p style="color:var(--text-dim);margin:0 0 12px;font-size:var(--sz-label)">
      Submit items for appraisal — prices from <a href="https://janice.e-351.com" target="_blank" rel="noopener">Janice</a>
      plus live ${escapeHtml(dest)} structure orders.
    </p>
    <div class="appraisal-panel">
      <div class="appraisal-route">
        <label>Market <select id="ap-market">${(apMeta.markets || [])
          .map(
            (m) =>
              `<option value="${escapeAttr(m.id)}"${m.id === "jita" ? " selected" : ""}>${escapeHtml(m.label)}</option>`
          )
          .join("")}</select></label>
        <span class="appraisal-arrow">→</span>
        <span class="appraisal-dest">${escapeHtml(dest)}</span>
      </div>
      <label class="appraisal-label">Items (any format: <code>Name x 248</code>, tab-separated from game)</label>
      <textarea id="ap-text" class="appraisal-textarea" rows="10" placeholder="Navy Cap Booster 3200 x248"></textarea>
      <div class="appraisal-actions">
        <button class="nav-btn primary" id="ap-run">Appraise</button>
        <a class="nav-btn" href="${escapeAttr(meta?.buyback_url || "#")}" target="_blank" rel="noopener">Corp buyback →</a>
      </div>
    </div>
    <div id="ap-results" class="hidden"></div>`;

  const resultsEl = document.getElementById("ap-results");
  const runBtn = document.getElementById("ap-run");

  if (!apMeta.janice_configured) {
    resultsEl.classList.remove("hidden");
    resultsEl.innerHTML =
      '<p class="loading-msg">Janice API key not set on market-api. Add <code>MARKET_JANICE_API_KEY</code> or <code>BUYBACKPROGRAM_PRICE_JANICE_API_KEY</code> to <code>.env</code> and rebuild.</p>';
    runBtn.disabled = true;
    return;
  }

  async function run() {
    const text = document.getElementById("ap-text").value.trim();
    if (!text) return;
    runBtn.disabled = true;
    resultsEl.classList.remove("hidden");
    resultsEl.innerHTML = '<div class="loading-msg">Appraising…</div>';
    try {
      const data = await api("/appraisal", {
        method: "POST",
        body: {
          text,
          sell_market: document.getElementById("ap-market").value,
        },
      });
      renderAppraisalResults(resultsEl, data, dest);
    } catch (e) {
      resultsEl.innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
    } finally {
      runBtn.disabled = false;
    }
  }

  runBtn.addEventListener("click", () => run());
}

function renderAppraisalResults(el, data, dest) {
  const t = data.totals || {};
  const market = data.sell_market_label || "JITA";
  el.innerHTML = `
    <div class="appraisal-results">
      <div class="appraisal-summary">
        <div class="appraisal-stat"><span class="label">Total Sell Value</span><strong>${fmtIsk(t.total_sell)}</strong></div>
        <div class="appraisal-stat"><span class="label">Split Value</span><strong>${fmtIsk(t.split_value)}</strong></div>
        <div class="appraisal-stat"><span class="label">Total Buy Value</span><strong>${fmtIsk(t.total_buy)}</strong></div>
        <div class="appraisal-stat"><span class="label">Total Volume</span><strong>${fmtVol(t.total_volume_m3)} m³</strong></div>
      </div>
      <p class="appraisal-meta-line">Market <strong>${escapeHtml(market)}</strong> · Destination <strong>${escapeHtml(data.destination_label || dest)}</strong>${data.janice_used ? " · Janice" : ""}</p>
      ${data.unresolved?.length ? `<p class="loading-msg">Unresolved: ${escapeHtml(data.unresolved.join(", "))}</p>` : ""}
      <div id="ap-table-wrap"></div>
    </div>`;
  const cols = [
    { label: "", col: "col-icon", sortKey: false, render: (r) => typeIconImg(r.type_id, 28) },
    {
      label: "Name",
      col: "col-item",
      sortKey: "name",
      sortValue: (r) => (r.name || "").toLowerCase(),
      defaultSortDir: "asc",
      render: (r) => escapeHtml(r.name),
    },
    { label: "Qty", sortKey: "quantity", class: "num", render: (r) => fmtVol(r.quantity) },
    { label: "Single Vol.", sortKey: "single_volume_m3", class: "num", render: (r) => (r.single_volume_m3 != null ? `${fmtVol(r.single_volume_m3)} m³` : "—") },
    { label: "Total Vol.", sortKey: "total_volume_m3", class: "num", render: (r) => (r.total_volume_m3 != null ? `${fmtVol(r.total_volume_m3)} m³` : "—") },
    { label: "Single Sell", sortKey: "single_sell", class: "num sell", defaultSortDir: "desc", render: (r) => fmtIsk(r.single_sell) },
    { label: "Single Buy", sortKey: "single_buy", class: "num buy", render: (r) => fmtIsk(r.single_buy) },
    { label: "Total Sell", sortKey: "total_sell", class: "num sell", render: (r) => fmtIsk(r.total_sell) },
    { label: "Total Buy", sortKey: "total_buy", class: "num buy", render: (r) => fmtIsk(r.total_buy) },
    { label: "Sell ISK/m³", sortKey: "sell_isk_per_m3", class: "num", render: (r) => (r.sell_isk_per_m3 != null ? fmtIsk(r.sell_isk_per_m3) : "—") },
    { label: "Buy ISK/m³", sortKey: "buy_isk_per_m3", class: "num", render: (r) => (r.buy_isk_per_m3 != null ? fmtIsk(r.buy_isk_per_m3) : "—") },
    { label: `${dest} sell`, sortKey: "wompstar_sell", class: "num sell", render: (r) => fmtIsk(r.wompstar_sell) },
    { label: `${dest} buy`, sortKey: "wompstar_buy", class: "num buy", render: (r) => fmtIsk(r.wompstar_buy) },
  ];
  const wrap = document.getElementById("ap-table-wrap");
  if (!data.lines?.length) {
    wrap.innerHTML = "<p class=\"loading-msg\">No priced lines.</p>";
    return;
  }
  mountSortableTable(wrap, cols, data.lines, {
    defaultSortKey: "total_sell",
    defaultSortDir: "desc",
  });
}

const PAGES = {
  home: pageHome,
  margin_finder: pageMarginFinder,
  "market-browser": pageMarketBrowser,
  market_trends: pageMarketTrends,
  contract_price: pageContractPrices,
  tradeVol_type: pageTradeVolType,
  price_compare: pagePriceCompare,
  pi_rank: pagePiRank,
  appraisal: pageAppraisal,
};

async function boot() {
  const panel = document.getElementById("main-panel");
  try {
    await loadMeta();
  } catch (e) {
    setStatus(false);
    panel.innerHTML =
      '<p class="loading-msg">Market API unavailable. Start <code>market-api</code> and check Caddy routes.</p>';
    return;
  }
  const r = route();
  const fn = PAGES[r] || pageHome;
  await fn(panel);
  renderNav();
}

boot();
