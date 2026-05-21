/**
 * EVE-EMU market tools SPA (path-based routes, Adam4EVE / isk.gg layout).
 */

const API = "/api/market/v1";

let meta = null;

async function api(path) {
  const r = await fetch(`${API}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
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

function tableHtml(columns, rows) {
  const colgroup = columns
    .map((c) => `<col class="${c.col || c.class || ""}"/>`)
    .join("");
  const th = columns
    .map((c) => {
      const cls = [c.col, c.class].filter(Boolean).join(" ");
      return `<th class="${cls}">${c.label}</th>`;
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

async function pageMarginFinder(panel) {
  panel.innerHTML = `<h2 style="margin:0 0 12px;font-size:var(--sz-title)">Margin finder</h2>
    <p style="color:var(--text-dim);margin:0 0 12px">Buy/sell spread at ${meta?.wompstar?.name}. Compare import from Jita in a later pass.</p>
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
        render: (r) =>
          typeIconImg(r.type_id, 32),
      },
      {
        label: "Item",
        col: "col-item",
        render: (r) => {
          const name = r.type_name || `Type ${r.type_id}`;
          const q = encodeURIComponent(name);
          return `<a href="/market-browser?name=${q}">${escapeHtml(name)}</a>`;
        },
      },
      {
        label: "Spread (ISK)",
        class: "num",
        render: (r) => fmtIsk(r.spread_isk ?? r.spread),
      },
      {
        label: "Spread %",
        key: "spread_pct",
        class: "num",
        render: (r) => (r.spread_pct != null ? `${r.spread_pct}%` : "—"),
      },
      {
        label: "Buy",
        class: "num buy",
        render: (r) => fmtIsk(r.buy_price),
      },
      {
        label: "Sell",
        class: "num sell",
        render: (r) => fmtIsk(r.sell_price),
      },
    ];
    const el = document.getElementById("mf-table");
    if (!data.rows?.length) {
      el.innerHTML =
        '<p class="loading-msg">No spreads yet. Ensure structure sync is configured.</p>';
      return;
    }
    el.innerHTML = tableHtml(cols, data.rows);
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
      Items listed at ${meta?.wompstar?.name || "WOMPSTAR"}. Search by in-game name.
    </p>
    <div class="mb-layout">
      <aside class="mb-sidebar" id="mb-sidebar">
        <div class="loading-msg">Loading catalog…</div>
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
  const suggestEl = document.getElementById("mb-suggest");
  const sidebarEl = document.getElementById("mb-sidebar");
  const bodyEl = document.getElementById("mb-body");

  let catalog = [];
  let categoryTree = [];
  let activeTypeId = null;
  let suggestFocus = -1;

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
      const kids = filterTree(node.children || [], needle);
      if (kids.length) out.push({ ...node, children: kids });
    }
    return out;
  }

  function renderTypeBtn(t) {
    const active = t.type_id === activeTypeId ? "active" : "";
    return `<li><button type="button" class="type-link ${active}" data-tid="${t.type_id}" data-name="${escapeAttr(t.name)}">
      ${typeIconImg(t.type_id, 20)}
      <span>${escapeHtml(t.name)}</span>
    </button></li>`;
  }

  function renderTreeNodes(nodes) {
    return nodes
      .map((node) => {
        if (node.kind === "type") return renderTypeBtn(node);
        const kids = node.children || [];
        if (!kids.length) return "";
        return `<li><details class="mb-cat" open><summary>${escapeHtml(node.name)}</summary><ul class="mb-cat-tree">${renderTreeNodes(kids)}</ul></details></li>`;
      })
      .join("");
  }

  function bindTypeButtons(root) {
    root.querySelectorAll("button.type-link[data-tid]").forEach((btn) => {
      btn.addEventListener("click", () =>
        selectItem(Number(btn.dataset.tid), btn.dataset.name)
      );
    });
  }

  function renderSidebar(filter = "") {
    const needle = filter.trim().toLowerCase();
    if (!catalog.length) {
      sidebarEl.innerHTML =
        '<div class="loading-msg">No listed items yet. Run structure sync.</div>';
      return;
    }
    let tree = filterTree(categoryTree, needle);
    if (!tree.length && !needle && catalog.length) {
      tree = catalog.map((t) => ({
        kind: "type",
        type_id: t.type_id,
        name: t.name,
      }));
    }
    if (!tree.length) {
      sidebarEl.innerHTML = needle
        ? '<div class="loading-msg">No matches in catalog.</div>'
        : '<div class="loading-msg">Run structure sync to load categories.</div>';
      return;
    }
    sidebarEl.innerHTML = `<ul class="mb-cat-tree">${renderTreeNodes(tree)}</ul>`;
    bindTypeButtons(sidebarEl);
  }

  async function loadItem(typeId, name) {
    bodyEl.innerHTML = '<div class="loading-msg">Loading orders…</div>';
    activeTypeId = typeId;
    searchEl.value = name;
    hideSuggestions();
    renderSidebar(searchEl.value);

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
      renderSidebar("");
      return;
    }
    renderSidebar(q);
    try {
      const { types } = await api(`/browser/search?q=${encodeURIComponent(q)}&limit=25`);
      showSuggestions(types);
    } catch {
      hideSuggestions();
    }
  }, 180);

  searchEl.addEventListener("input", fetchSuggestions);
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
    const [cat, cats] = await Promise.all([
      api("/browser/catalog"),
      api("/browser/categories"),
    ]);
    catalog = cat.types || [];
    categoryTree = cats.tree || [];
    renderSidebar("");
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
    } else if (catalog[0]) {
      await loadItem(catalog[0].type_id, catalog[0].name);
    } else {
      bodyEl.innerHTML =
        '<div class="loading-msg">No listed items yet. Run structure sync from admin.</div>';
    }
  } catch (e) {
    sidebarEl.innerHTML = `<div class="loading-msg">${escapeHtml(e.message)}</div>`;
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
    <p style="color:var(--text-dim)">Top buy/sell spreads at ${meta?.wompstar?.name} (full category boards coming later).</p>
    <div id="mt-table"><div class="loading-msg">Loading…</div></div>`;
  try {
    const data = await api("/margin/finder?limit=80");
    const cols = [
      { label: "", col: "col-icon", render: (r) => typeIconImg(r.type_id, 28) },
      {
        label: "Item",
        col: "col-item",
        render: (r) => {
          const n = r.type_name || `Type ${r.type_id}`;
          return `<a href="/market-browser?name=${encodeURIComponent(n)}">${escapeHtml(n)}</a>`;
        },
      },
      { label: "Spread (ISK)", class: "num", render: (r) => fmtIsk(r.spread_isk) },
      { label: "Spread %", class: "num", render: (r) => `${r.spread_pct}%` },
    ];
    document.getElementById("mt-table").innerHTML = data.rows?.length
      ? tableHtml(cols, data.rows)
      : '<p class="loading-msg">No data.</p>';
  } catch (e) {
    document.getElementById("mt-table").innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
  }
}

async function pagePriceCompare(panel) {
  panel.innerHTML = `<h2 style="margin:0 0 8px">Price compare</h2>
    <p style="color:var(--text-dim)">WOMPSTAR hub prices (Jita/import column when region sync is added).</p>
    <div id="pc-table"><div class="loading-msg">Loading…</div></div>`;
  try {
    const { types } = await api("/browser/catalog");
    const rows = (types || []).slice(0, 120);
    const cols = [
      { label: "", col: "col-icon", render: (r) => typeIconImg(r.type_id, 28) },
      {
        label: "Item",
        col: "col-item",
        render: (r) =>
          `<a href="/market-browser?name=${encodeURIComponent(r.name)}">${escapeHtml(r.name)}</a>`,
      },
      { label: "WOMP sell", class: "num sell", render: (r) => fmtIsk(r.best_sell) },
      { label: "WOMP buy", class: "num buy", render: (r) => fmtIsk(r.best_buy) },
      { label: "Jita", class: "num", render: () => "—" },
    ];
    document.getElementById("pc-table").innerHTML = rows.length
      ? tableHtml(cols, rows)
      : '<p class="loading-msg">No catalog.</p>';
  } catch (e) {
    document.getElementById("pc-table").innerHTML = `<p class="loading-msg">${escapeHtml(e.message)}</p>`;
  }
}

const PAGES = {
  home: pageHome,
  margin_finder: pageMarginFinder,
  "market-browser": pageMarketBrowser,
  market_trends: pageMarketTrends,
  contract_price: (p) =>
    pageStub(
      p,
      "Contract prices",
      "WOMP alliance contract history grid (BPC ME/TE) — Adam4EVE contract_price style."
    ),
  tradeVol_type: (p) =>
    pageStub(
      p,
      "Trade volume by type",
      "Volume at WOMPSTAR vs import region."
    ),
  price_compare: pagePriceCompare,
  pi_rank: (p) =>
    pageStub(
      p,
      "PI profitability",
      "PI chain chart with WOMPSTAR selectable as sale location."
    ),
  appraisal: (p) =>
    pageStub(
      p,
      "Appraisal",
      "Paste item list; links to corp buyback calculator."
    ),
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
