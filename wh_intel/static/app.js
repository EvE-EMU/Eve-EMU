(() => {
  const canvas = document.getElementById("map");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const feedEl = document.getElementById("feed");

  let overlay = { systems: [], jumps: [], rings: [], bubbles: [] };
  const sysById = new Map();
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  const portraitCache = new Map();

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    draw();
  }

  function worldToScreen(x, y) {
    const cx = canvas.width / 2 + panX;
    const cy = canvas.height / 2 + panY;
    return [cx + x * scale, cy + y * scale];
  }

  function screenToWorld(sx, sy) {
    const cx = canvas.width / 2 + panX;
    const cy = canvas.height / 2 + panY;
    return [(sx - cx) / scale, (sy - cy) / scale];
  }

  function loadPortrait(url) {
    if (!url || portraitCache.has(url)) return portraitCache.get(url);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = url;
    portraitCache.set(url, img);
    img.onload = () => draw();
    return img;
  }

  function draw() {
    ctx.fillStyle = "#05070a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    overlay.jumps.forEach((j) => {
      const a = sysById.get(j.from);
      const b = sysById.get(j.to);
      if (!a || !b) return;
      const [x1, y1] = worldToScreen(a.x, a.y);
      const [x2, y2] = worldToScreen(b.x, b.y);
      ctx.strokeStyle = "#2ea043";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    });

    overlay.bubbles.forEach((b) => {
      const a = sysById.get(b.from_system_id);
      const to = sysById.get(b.to_system_id);
      if (!a || !to) return;
      const t = b.side === "from" ? 0.22 : 0.78;
      const mx = a.x + (to.x - a.x) * t;
      const my = a.y + (to.y - a.y) * t;
      const [sx, sy] = worldToScreen(mx, my);
      const r = 28 * scale;
      ctx.strokeStyle = "#a371f7";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "rgba(163,113,247,0.15)";
      ctx.fill();
      ctx.fillStyle = "#c9d1d9";
      ctx.font = `${Math.max(10, 10 * scale)}px sans-serif`;
      ctx.fillText("BUBBLE", sx - 22 * scale, sy + 4);
    });

    const activeSystems = new Set(overlay.rings.map((r) => r.system_id));
    overlay.systems.forEach((s) => {
      const [sx, sy] = worldToScreen(s.x, s.y);
      if (activeSystems.has(s.id)) {
        const pulse = 18 + 6 * Math.sin(Date.now() / 400);
        ctx.strokeStyle = "rgba(255,107,61,0.85)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(sx, sy, pulse * scale, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = activeSystems.has(s.id) ? "#ff6b3d" : "#58a6ff";
      ctx.beginPath();
      ctx.arc(sx, sy, 6 * scale, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#e6edf3";
      ctx.font = `${Math.max(11, 11 * scale)}px sans-serif`;
      ctx.fillText(s.name, sx + 10, sy - 8);
      if (s.tags && s.tags.length) {
        ctx.fillStyle = "#8b949e";
        ctx.font = `${Math.max(9, 9 * scale)}px sans-serif`;
        ctx.fillText(s.tags.map((t) => t.tag).join(" · "), sx + 10, sy + 12);
      }
    });
  }

  function renderFeed() {
    feedEl.innerHTML = "";
    overlay.rings.forEach((r) => {
      const div = document.createElement("div");
      div.className = "feed-item";
      const ents = (r.entities || [])
        .map((e) => {
          const img = e.portrait_url
            ? `<img src="${e.portrait_url}" alt="" loading="lazy" />`
            : "";
          return `<span class="entity">${img}${e.name}</span>`;
        })
        .join("");
      div.innerHTML = `
        <div class="sys">${r.system_name}</div>
        <div class="meta">${r.channel} · ${r.remaining_seconds}s left</div>
        <div class="entities">${ents}</div>
        <div class="meta">${r.raw_line.replace(/<[^>]+>/g, "")}</div>
      `;
      feedEl.appendChild(div);
      (r.entities || []).forEach((e) => loadPortrait(e.portrait_url));
    });
  }

  async function refresh() {
    try {
      const res = await fetch("/intel/api/v1/overlay");
      overlay = await res.json();
      sysById.clear();
      overlay.systems.forEach((s) => sysById.set(s.id, s));
      statusEl.textContent = `${overlay.rings.length} active ring(s)`;
      renderFeed();
      draw();
    } catch (err) {
      statusEl.textContent = "API error";
      console.error(err);
    }
  }

  function nearestJump(wx, wy) {
    let best = null;
    let bestD = Infinity;
    overlay.jumps.forEach((j) => {
      const a = sysById.get(j.from);
      const b = sysById.get(j.to);
      if (!a || !b) return;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const d = Math.hypot(mx - wx, my - wy);
      if (d < bestD) {
        bestD = d;
        best = j;
      }
    });
    return bestD < 40 / scale ? best : null;
  }

  canvas.addEventListener("click", async (ev) => {
    const rect = canvas.getBoundingClientRect();
    const [wx, wy] = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
    const jump = nearestJump(wx, wy);
    if (!jump) return;
    const side = prompt("Bubble side on this gate? Type 'from' (near first system) or 'to'", "from");
    if (side !== "from" && side !== "to") return;
    await fetch("/intel/api/v1/bubbles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        from_system_id: jump.from,
        to_system_id: jump.to,
        side,
        note: "anchored bubble",
      }),
    });
    refresh();
  });

  canvas.addEventListener("mousedown", (ev) => {
    dragging = true;
    lastX = ev.clientX;
    lastY = ev.clientY;
    canvas.style.cursor = "grabbing";
  });
  window.addEventListener("mouseup", () => {
    dragging = false;
    canvas.style.cursor = "grab";
  });
  window.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    panX += ev.clientX - lastX;
    panY += ev.clientY - lastY;
    lastX = ev.clientX;
    lastY = ev.clientY;
    draw();
  });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    scale *= ev.deltaY > 0 ? 0.9 : 1.1;
    scale = Math.max(0.2, Math.min(8, scale));
    draw();
  });

  window.addEventListener("resize", resize);
  resize();
  refresh();
  setInterval(refresh, 5000);
  setInterval(draw, 250);
})();
