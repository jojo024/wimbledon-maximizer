// Shared helpers for Wimbledon$ Maximizer.
// The currency is the Wimbledon (plural: Wimbledons), written W$ —
// a W struck through like a dollar sign. WIM_SVG is that glyph.

export const WIM_SVG = `<svg class="wim-glyph" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"
  aria-label="Wimbledons" role="img">
  <path d="M3 6 L7.5 18 L12 9 L16.5 18 L21 6"/>
  <path d="M12 2.5 V21.5"/>
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

export function starBar(avg, count, interactive) {
  const full = Math.round(avg);
  return `<span class="stars${interactive ? "" : " locked"}" data-avg="${avg}">
    ${[1, 2, 3, 4, 5].map(i =>
      `<span data-star="${i}" class="${i <= full ? "on" : ""}">&#9733;</span>`).join("")}
  </span><span class="rating-meta">${avg ? avg.toFixed(1) : "–"} (${count})</span>`;
}
