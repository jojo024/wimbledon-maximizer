// Shared helpers for Wimbledon$ Maximizer.
// The currency is the Wimbledon (plural: Wimbledons). The glyph is a W with a
// horizontal strikethrough (like the Won or Yen symbols) rather than a dollar
// sign's vertical stroke. "Wimbledon$" remains the written/spoken form in copy.

export const WIM_SVG = `<svg class="wim-glyph" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"
  aria-label="Wimbledons" role="img">
  <path d="M3 6 L7.5 18 L12 9 L16.5 18 L21 6"/>
  <path d="M2 12 H22"/>
</svg>`;

// cents -> "30.00" / "12.50" — always two decimals, so every price in the UI lines up
export function fmtW(cents) {
  return (cents / 100).toFixed(2);
}

// cents -> inline W$ amount markup
export function wim(cents) {
  return `<span class="wim">${WIM_SVG}<span>${fmtW(cents)}</span></span>`;
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// A deterministic, purely cosmetic "barcode" rendered from an arbitrary card
// number — every character maps to a fixed bar-width pattern derived from its
// char code, so the same number always draws the same bars. This is not a
// real Code39/Code128 encoding (no external library, no network request, and
// no scanner needs to read it back) — it's flavor for sharing a card, not a
// functional redemption mechanism.
export function renderBarcode(cardNumber) {
  const clean = String(cardNumber).trim().slice(0, 30);
  const GAP = 1; // tight spacing — real barcodes read as near-continuous bars
  let x = 4;
  const bars = [];
  const addBar = w => {
    bars.push(`<rect x="${x}" y="4" width="${w}" height="56" fill="#000"/>`);
    x += w + GAP;
  };

  addBar(3); addBar(1); addBar(3); // start guard pattern
  for (const ch of clean) {
    const code = ch.charCodeAt(0);
    for (let i = 0; i < 5; i++) {
      const w = 1 + ((code >> (i * 2)) & 3); // 1-4px, narrow-dominant like a real barcode
      addBar(w);
    }
  }
  addBar(3); addBar(1); addBar(3); // end guard pattern
  x += 4;

  return `<svg viewBox="0 0 ${x} 76" width="100%" height="100" xmlns="http://www.w3.org/2000/svg"
    role="img" aria-label="Barcode for card ${esc(clean)}">
    <rect x="0" y="0" width="${x}" height="76" fill="#fff"/>
    ${bars.join("")}
    <text x="${x / 2}" y="72" font-size="11" text-anchor="middle" fill="#000"
      font-family="monospace" letter-spacing="1">${esc(clean)}</text>
  </svg>`;
}

export function renderNav(active) {
  const links = [
    ["/", "Leaderboard"],
    ["/builder", "Basket Builder"],
    ["/tips", "Tips & Tricks"],
    ["/meals", "Add Meals"],
    ["/play", "🍓 Play"],
    ["/admin", "Admin"],
  ];
  const nav = document.createElement("nav");
  nav.className = "wim-nav";
  nav.innerHTML = `
    <a class="logo" href="/">${WIM_SVG}<span>Wimbledon$ Maximizer</span></a>
    <span class="spacer"></span>
    ${links.map(([href, label]) =>
      `<a class="navlink${href === active ? " active" : ""}" href="${href}">${label}</a>`).join("")}
  `;
  document.body.prepend(nav);
}

export async function api(method, url, body, adminKey) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (adminKey) headers["X-Admin-Key"] = adminKey;
  const res = await fetch(url, {
    method, headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const detail = (await res.json()).detail;
      if (typeof detail === "string") msg = detail;
      // FastAPI/pydantic validation errors (422) return `detail` as a list of
      // {loc, msg, type} objects, not a string — join their messages instead
      // of letting new Error() stringify the array into "[object Object],...".
      else if (Array.isArray(detail) && detail.length) {
        msg = detail.map(d => d.msg || JSON.stringify(d)).join("; ");
      }
    } catch { /* keep status */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

let toastEl = null;
export function toast(msg, isError = false) {
  if (!toastEl) {
    toastEl = document.createElement("div");
    toastEl.className = "toast";
    document.body.appendChild(toastEl);
  }
  toastEl.textContent = msg;
  toastEl.classList.toggle("err", isError);
  toastEl.classList.add("show");
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => toastEl.classList.remove("show"), 2600);
}

// avg/count drive the display; `mine` (1-5 or null) is the caller's own vote.
// Stars stay interactive so a vote can be changed; `mine` just adds a note.
export function starBar(avg, count, interactive, mine = null) {
  const full = Math.round(avg);
  const note = mine ? `<span class="rating-meta mine">your vote: ${mine}&#9733;</span>` : "";
  return `<span class="stars${interactive ? "" : " locked"}" data-avg="${avg}">
    ${[1, 2, 3, 4, 5].map(i =>
      `<span data-star="${i}" class="${i <= full ? "on" : ""}">&#9733;</span>`).join("")}
  </span><span class="rating-meta">${avg ? avg.toFixed(1) : "–"} (${count})</span>${note}`;
}

// ---------- session identity ----------

let _session = null; // { voter_id, name }

// Fetch (once) the caller's session. The GET also sets the signed cookie.
export async function getSession() {
  if (!_session) _session = await api("GET", "/api/session");
  return _session;
}

export async function saveName(name) {
  name = String(name).trim();
  if (!name) return _session;
  await api("POST", "/api/session/name", { name });
  if (_session) _session.name = name; else _session = { name };
  return _session;
}

// Modal asking for a display name. Resolves to the name, or "" if skipped.
// required=true drops the Skip button and the click-outside-to-dismiss —
// used when the caller is about to post something and must have a name first.
export function namePrompt(required = false) {
  return new Promise(resolve => {
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `
      <div class="modal">
        <h3>${WIM_SVG} Who's maximizing?</h3>
        <p>${required
          ? "Pick a name before you post — it's how your combos, deals, and comments are attributed. You can change it later, but never per-post."
          : "Pick a name so your combos and comments carry your handle. You can change it anytime."}</p>
        <form class="name-form">
          <input name="name" placeholder="Your handle" maxlength="40" autocomplete="off" required>
          <div class="modal-actions">
            ${required ? "" : `<button type="button" class="btn btn-sm" data-skip>Skip</button>`}
            <button class="btn btn-sm btn-green">Save</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(ov);
    const input = ov.querySelector("input");
    input.focus();
    const close = val => { ov.remove(); resolve(val); };
    if (!required) {
      ov.querySelector("[data-skip]").onclick = () => close("");
      ov.addEventListener("click", e => { if (e.target === ov) close(""); });
    }
    ov.querySelector(".name-form").addEventListener("submit", async e => {
      e.preventDefault();
      const name = input.value.trim();
      if (!name) return required ? null : close("");
      try { await saveName(name); } catch { /* non-fatal */ }
      close(name);
    });
  });
}

// Resolve the caller's display name, prompting (mandatory) if none is set yet.
// Returns "" only if somehow still unset (should not happen with required=true).
export async function ensureNamed() {
  const s = await getSession();
  if (s.name) return s.name;
  const name = await namePrompt(true);
  if (name) s.name = name;
  return name;
}

// "Posting as <name>" — read-only identity, no free-text author field anywhere
// a post is made, and no way to change it once set (the server rejects a
// second /api/session/name call, so there's deliberately no UI for it either).
export function identityLine(name) {
  return `<div class="identity-line">Posting as <b>${esc(name)}</b></div>`;
}

// ---------- floating basket (drag-and-drop meal chips) ----------

// Scatters `meals` as draggable chips inside `arena`; dropping one on `basketEl`
// calls onDrop(mealId). Chips continuously wander the arena (bouncing off its
// edges and off the basket itself, screensaver-style) while also bobbing via
// the .float-chip CSS animation — two independent motions on nested elements
// (wrap moves, inner chip bobs) so their `transform`s don't fight each other
// or the drag gesture. The chip being dragged bumps nearby wanderers aside.
export function initFloatingBasket({ arena, basketEl, meals, onDrop }) {
  arena.querySelectorAll(".chip-wrap").forEach(el => el.remove());
  const wanderers = [];
  const CHIP_W = 100, CHIP_H = 78;

  meals.forEach((m, i) => {
    const wrap = document.createElement("div");
    wrap.className = "chip-wrap";
    const chip = document.createElement("div");
    chip.className = "float-chip";
    chip.dataset.id = m.id;
    chip.style.animationDelay = `${(i * 0.45) % 4}s`;
    chip.style.animationDuration = `${4.5 + (i % 4) * 0.7}s`;
    chip.innerHTML = `<span class="emoji">${esc(m.emoji)}</span>
      <span class="cname">${esc(m.name)}</span>
      <span class="cprice">W$ ${fmtW(m.price_cents)}</span>`;
    wrap.appendChild(chip);
    arena.appendChild(wrap);

    const w = arena.clientWidth, h = arena.clientHeight;
    const cx = w / 2, cy = h / 2;
    const ring = i % 2;
    const count = Math.ceil(meals.length / 2);
    const angle = ((Math.floor(i / 2) / count) * 2 * Math.PI) + ring * 0.5 + (i % 3) * 0.15;
    const rx = (ring ? 0.44 : 0.31) * w;
    const ry = (ring ? 0.40 : 0.27) * h;
    const x = Math.min(Math.max(cx + Math.cos(angle) * rx - 45, 4), w - CHIP_W);
    const y = Math.min(Math.max(cy + Math.sin(angle) * ry - 34, 4), h - CHIP_H);
    wrap.style.left = `${x}px`;
    wrap.style.top = `${y}px`;

    const speed = 10 + Math.random() * 14; // px/sec — gentle, but unmistakably alive
    const dir = Math.random() * Math.PI * 2;
    wanderers.push({
      el: wrap, x, y, vx: Math.cos(dir) * speed, vy: Math.sin(dir) * speed, dragging: false,
    });
  });

  // Basket's box in arena-relative coordinates, padded — treated as a wall.
  function basketZone(pad = 16) {
    return {
      left: basketEl.offsetLeft - pad, top: basketEl.offsetTop - pad,
      right: basketEl.offsetLeft + basketEl.offsetWidth + pad,
      bottom: basketEl.offsetTop + basketEl.offsetHeight + pad,
    };
  }

  let lastT = null;
  function tick(t) {
    if (lastT == null) lastT = t;
    const dt = Math.min((t - lastT) / 1000, 0.05); // clamp so a stalled tab doesn't teleport chips
    lastT = t;
    const w = arena.clientWidth, h = arena.clientHeight;
    const maxX = w - CHIP_W, maxY = h - CHIP_H;
    const bz = basketZone();
    for (const p of wanderers) {
      if (p.dragging) continue;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (p.x < 4) { p.x = 4; p.vx = Math.abs(p.vx); }
      if (p.x > maxX) { p.x = maxX; p.vx = -Math.abs(p.vx); }
      if (p.y < 4) { p.y = 4; p.vy = Math.abs(p.vy); }
      if (p.y > maxY) { p.y = maxY; p.vy = -Math.abs(p.vy); }
      // Bounce off the basket like a wall: push out along whichever edge is
      // closest, so the drop zone stays clear instead of getting drifted over.
      if (p.x < bz.right && p.x + CHIP_W > bz.left && p.y < bz.bottom && p.y + CHIP_H > bz.top) {
        const penLeft = (p.x + CHIP_W) - bz.left, penRight = bz.right - p.x;
        const penTop = (p.y + CHIP_H) - bz.top, penBottom = bz.bottom - p.y;
        const minPen = Math.min(penLeft, penRight, penTop, penBottom);
        if (minPen === penLeft) { p.x = bz.left - CHIP_W; p.vx = -Math.abs(p.vx); }
        else if (minPen === penRight) { p.x = bz.right; p.vx = Math.abs(p.vx); }
        else if (minPen === penTop) { p.y = bz.top - CHIP_H; p.vy = -Math.abs(p.vy); }
        else { p.y = bz.bottom; p.vy = Math.abs(p.vy); }
      }
      p.el.style.left = `${p.x}px`;
      p.el.style.top = `${p.y}px`;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  let drag = null;

  function endDrag(dropped) {
    if (!drag) return;
    if (dropped) onDrop(Number(drag.chip.dataset.id));
    drag.chip.classList.remove("dragging");
    drag.chip.style.transform = "";
    if (drag.wanderer) drag.wanderer.dragging = false;
    basketEl.classList.remove("hot");
    drag = null;
  }

  arena.addEventListener("pointerdown", e => {
    const chip = e.target.closest(".float-chip");
    if (!chip) return;
    e.preventDefault();
    chip.setPointerCapture(e.pointerId);
    const wanderer = wanderers.find(p => p.el === chip.parentElement);
    if (wanderer) wanderer.dragging = true;
    drag = { chip, wanderer, startX: e.clientX, startY: e.clientY };
    chip.classList.add("dragging");
  });

  arena.addEventListener("pointermove", e => {
    if (!drag) return;
    drag.chip.style.transform =
      `translate(${e.clientX - drag.startX}px, ${e.clientY - drag.startY}px) scale(1.08)`;
    const b = basketEl.getBoundingClientRect();
    const over = e.clientX > b.left && e.clientX < b.right && e.clientY > b.top && e.clientY < b.bottom;
    basketEl.classList.toggle("hot", over);

    // Bump nearby wanderers away from the dragged chip's current position —
    // an impulse to their velocity; the tick loop above carries it forward.
    const dragRect = drag.chip.getBoundingClientRect();
    const dcx = dragRect.left + dragRect.width / 2, dcy = dragRect.top + dragRect.height / 2;
    const BUMP_RADIUS = 75, BUMP_FORCE = 70, MAX_SPEED = 160;
    for (const p of wanderers) {
      if (p === drag.wanderer || p.dragging) continue;
      const r = p.el.getBoundingClientRect();
      const pcx = r.left + r.width / 2, pcy = r.top + r.height / 2;
      const dx = pcx - dcx, dy = pcy - dcy;
      const dist = Math.hypot(dx, dy);
      if (dist > 0.01 && dist < BUMP_RADIUS) {
        const force = (1 - dist / BUMP_RADIUS) * BUMP_FORCE;
        p.vx += (dx / dist) * force;
        p.vy += (dy / dist) * force;
        const sp = Math.hypot(p.vx, p.vy);
        if (sp > MAX_SPEED) { p.vx = (p.vx / sp) * MAX_SPEED; p.vy = (p.vy / sp) * MAX_SPEED; }
      }
    }
  });

  arena.addEventListener("pointerup", e => {
    if (!drag) return;
    const b = basketEl.getBoundingClientRect();
    const over = e.clientX > b.left && e.clientX < b.right && e.clientY > b.top && e.clientY < b.bottom;
    endDrag(over);
  });

  arena.addEventListener("pointercancel", () => endDrag(false));
}

// ---------- live feed ----------

// Subscribe to /ws/feed. Calls onEvent(event) for each broadcast; auto-reconnects.
export function connectFeed(onEvent) {
  let ws, retry = 0, closed = false;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  function open() {
    ws = new WebSocket(`${proto}://${location.host}/ws/feed`);
    ws.onmessage = e => {
      try { onEvent(JSON.parse(e.data)); } catch { /* ignore malformed */ }
    };
    ws.onopen = () => { retry = 0; };
    ws.onclose = () => {
      if (closed) return;
      retry = Math.min(retry + 1, 6);
      setTimeout(open, 500 * 2 ** (retry - 1)); // backoff, capped ~16s
    };
    ws.onerror = () => ws.close();
  }
  open();
  return () => { closed = true; if (ws) ws.close(); };
}
