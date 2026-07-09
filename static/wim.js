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

// cents -> "30" / "12.50"
export function fmtW(cents) {
  const v = (cents / 100).toFixed(2);
  return v.endsWith(".00") ? v.slice(0, -3) : v;
}

// cents -> inline W$ amount markup
export function wim(cents) {
  return `<span class="wim">${WIM_SVG}<span>${fmtW(cents)}</span></span>`;
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function renderNav(active) {
  const links = [
    ["/", "Leaderboard"],
    ["/builder", "Basket Builder"],
    ["/deals", "Daily Deal"],
    ["/players", "Players"],
    ["/meals", "Add Meals"],
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
    try { msg = (await res.json()).detail || msg; } catch { /* keep status */ }
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

// "Posting as <name> · change" — read-only identity, no free-text author field
// anywhere a post is made. The change link deliberately reopens the (skippable)
// prompt so switching handles is always an explicit, separate action.
export function identityLine(name) {
  return `<div class="identity-line">Posting as <b>${esc(name)}</b>
    <button type="button" class="link-btn" data-change-name>change</button></div>`;
}

// Wire up any [data-change-name] buttons within `root` to reopen the name prompt.
export function wireIdentityChange(root, onChanged) {
  root.querySelectorAll("[data-change-name]").forEach(btn => {
    btn.onclick = async () => {
      const name = await namePrompt(false);
      if (name) onChanged(name);
    };
  });
}

// ---------- floating basket (drag-and-drop meal chips) ----------

// Scatters `meals` as draggable chips inside `arena`; dropping one on `basketEl`
// calls onDrop(mealId). Chips continuously wander the arena (bouncing off its
// edges, screensaver-style) while also bobbing via the .float-chip CSS
// animation — two independent motions on nested elements (wrap moves, inner
// chip bobs) so their `transform`s don't fight each other or the drag gesture.
export function initFloatingBasket({ arena, basketEl, meals, onDrop }) {
  arena.querySelectorAll(".chip-wrap").forEach(el => el.remove());
  const wanderers = [];

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
    const x = Math.min(Math.max(cx + Math.cos(angle) * rx - 45, 4), w - 100);
    const y = Math.min(Math.max(cy + Math.sin(angle) * ry - 34, 4), h - 78);
    wrap.style.left = `${x}px`;
    wrap.style.top = `${y}px`;

    const speed = 10 + Math.random() * 14; // px/sec — gentle, but unmistakably alive
    const dir = Math.random() * Math.PI * 2;
    wanderers.push({
      el: wrap, x, y, vx: Math.cos(dir) * speed, vy: Math.sin(dir) * speed, dragging: false,
    });
  });

  let lastT = null;
  function tick(t) {
    if (lastT == null) lastT = t;
    const dt = Math.min((t - lastT) / 1000, 0.05); // clamp so a stalled tab doesn't teleport chips
    lastT = t;
    const w = arena.clientWidth, h = arena.clientHeight;
    const maxX = w - 100, maxY = h - 78;
    for (const p of wanderers) {
      if (p.dragging) continue;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (p.x < 4) { p.x = 4; p.vx = Math.abs(p.vx); }
      if (p.x > maxX) { p.x = maxX; p.vx = -Math.abs(p.vx); }
      if (p.y < 4) { p.y = 4; p.vy = Math.abs(p.vy); }
      if (p.y > maxY) { p.y = maxY; p.vy = -Math.abs(p.vy); }
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
