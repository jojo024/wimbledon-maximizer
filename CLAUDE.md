# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

**Wimbledon$ Maximizer** — a locally hosted FastAPI + SQLite web app. Users log meals (name, emoji, price in **Wimbledons**, the fake currency) and build a daily basket in the Basket Builder; the in-progress basket autosaves per session so it can be picked up later and submitted (once — one Daily Deal per calendar day) at day's end. Any total logs that day's Daily Deal (tracked on the all-time **Players** leaderboard, ranked by closeness to 30); land on **exactly 30 Wimbledons** and the same basket *also* enters the competition on the landing page, where combos are rated and commented on. One arena, one submit action, two possible outcomes. Admins can also seed the leaderboard with **honourable mention** combos — real 30-Wimbledon combinations that are visible and rateable but excluded from the competitive ranking, purely for fun. A **Tips & Tricks** board lets users share advice and react to it (up/down plus fire/heart/laugh/cry). Every visitor gets a signed session cookie and a display name; that name is always the server-derived author of anything they post — never a client-supplied string. An admin console edits the whole database.

## Commands

```bash
pip install -r requirements.txt
python main.py                      # serves on http://localhost:8030
WIM_PORT=9000 python main.py        # custom port
WIM_ADMIN_KEY=secret python main.py # custom admin key (default: "wimbledon")
```

Deploying beyond a trusted LAN: see [README.md § Deploying on the internet](README.md#deploying-on-the-internet)
and `deploy/` (Caddyfile, systemd unit, env template). Set `WIM_HOST=127.0.0.1`
together with a reverse proxy on the same host — uvicorn's own `forwarded_allow_ips`
(default `127.0.0.1`) then trusts that proxy's `X-Forwarded-For`/`Proto` headers
automatically; never bind `0.0.0.0` while also widening `WIM_FORWARDED_ALLOW_IPS`.

No test suite. Smoke-test after changes:

```bash
curl -s http://127.0.0.1:8030/api/meals | head -c 200
curl -s -c /tmp/jar.txt http://127.0.0.1:8030/api/session   # mints the session cookie
curl -s -b /tmp/jar.txt -X POST http://127.0.0.1:8030/api/session/name \
  -H "Content-Type: application/json" -d '{"name":"t"}'    # posting requires a name first
curl -s -b /tmp/jar.txt -X POST http://127.0.0.1:8030/api/combos -H "Content-Type: application/json" \
  -d '{"name":"t","items":[{"meal_id":3,"qty":1},{"meal_id":8,"qty":1},{"meal_id":7,"qty":1},{"meal_id":2,"qty":1}]}'
# seed meal ids 3+8+7+2 = 1200+1000+500+300 cents = exactly 30 Wimbledons; author is server-derived, never client-supplied
curl -s http://127.0.0.1:8030/api/admin/verify -H "X-Admin-Key: wimbledon"
```

Delete `wimbledon.db` to reset to seed data.

## Hard rules

- **The currency is always plural: "Wimbledons".** Never "30 Wimbledon", never "Wimbledon dollars". That plural is the joke and it is load-bearing. UI copy, API error messages, docs — everywhere.
- **The W$ symbol** is the SVG glyph in `static/wim.js` (`WIM_SVG`): a W with a horizontal strikethrough (Won/Yen-style, not a dollar sign's vertical stroke). Use `wim(cents)` for every price shown in the UI; do not hand-write "W$" strings in HTML except where a plain-text fallback is unavoidable. "Wimbledon$" (with a literal dollar sign) is still the correct written/spoken form in prose and headings — only the glyph's stroke changed.
- **Prices are integer cents** (`price_cents`, 3000 = 30 Wimbledons). Never store or compare floats. API request bodies take `price` as a float in Wimbledons and convert with `round(price * 100)` at the boundary.
- **Combo items are snapshots.** `combo_items` copies name/emoji/price_cents at submission time. Never join combos back to `meals` — meals are editable/deletable and combos must stay historically exact.
- **Colour scheme is purple/green futuristic dark.** All colours come from the tokens at the top of `static/style.css` (`--purple*`, `--green*`, glass tokens). Do not introduce new hex values outside the token block.
- **No emojis in docs, commit messages, or code comments.** Food emojis as app data (meal records, picker grid, seed rows) are the product and are fine.
- **Author identity is always server-derived, never client-supplied, and permanent once set.** Every write endpoint (`add_meal`, `add_combo`, `add_comment`, `submit_deal`) pulls the author from `sessions.display_name` via `require_named()`; request models have no `author`/`created_by` field to spoof. `/api/session/name` only succeeds once per session (a second call 400s) — there is no "change your name" flow anywhere, frontend or backend. Frontend forms show a read-only "Posting as `<name>`" line, never an editable text box.
- **Never re-parse `X-Forwarded-For`/`X-Forwarded-Proto` in application code.** uvicorn's own `ProxyHeadersMiddleware` already resolves `request.client`/`request.url.scheme` from those headers, gated to `FORWARDED_ALLOW_IPS` (default `127.0.0.1`) — `client_ip()`/`is_https()` just read the already-resolved values. A second, independent reimplementation is exactly how a subtle bug (e.g. taking the first entry of a comma-separated chain instead of the last, trusted one) turns into a spoofable rate limit or a wrongly-set cookie `Secure` flag.

## Architecture

Single-process FastAPI app, everything in `main.py`:

1. **Schema + seed** — `init_db()` creates 13 tables (`meals`, `combos` — with an `honourable` flag, `combo_items`, `ratings`, `comments`, `sessions`, `comment_votes`, `daily_deals`, `daily_deal_items`, `tips`, `tip_votes` — legacy, migrated away from and no longer written to, `tip_reactions`, `basket_drafts`) and seeds 18 meals + 2 combos when `meals` is empty. SQLite file `wimbledon.db` lives next to `main.py`; connections are opened per-request via `db()` with `PRAGMA foreign_keys = ON` (cascade deletes handle ratings/comments/items/votes/reactions when a combo, comment, tip, or meal is removed).
2. **Session identity** — `get_voter()` mints a signed HMAC cookie (`wim_session`) on first visit; `require_named()` resolves the caller's `sessions.display_name` and 400s if unset. Every write endpoint uses this as the author — request bodies carry no author field at all.
3. **Public API** — meals CRUD, combo submission (validates total == 3000 cents), ratings (one per voter, upsert), comments + comment upvotes, Daily Deal submission (one per voter **per calendar day, strictly — a second attempt the same day 400s**, any total) and its two leaderboards (`today`, all-time `leaderboard` with streaks), tips + six independent reactions per tip (`up`/`down`/`fire`/`heart`/`laugh`/`cry`; only up/down feed the sort score), and the per-user basket draft (`GET`/`PUT /api/basket`, scoped to `(voter_id, today)` — an autosave of the in-progress Basket Builder, not a finalized submission; cleared server-side when that day's deal is submitted).
4. **Live feed** — `/ws/feed` WebSocket; `ConnectionManager` broadcasts `combo_new`/`combo_update`/`combo_delete`/`rating`/`comment`/`comment_vote`/`deal`/`tip_new`/`tip_react`/`tip_update`/`tip_delete` events fired from `notify()` after each write.
5. **Admin API** — all under `/api/admin/*`, guarded by `require_admin()` comparing the `X-Admin-Key` header to `WIM_ADMIN_KEY`. Covers meals, combos (incl. item editor preserving the 3000-cent invariant, and `POST /api/admin/combos` to create an honourable-mention combo directly), ratings, comments (edit + delete), daily deals, and tips (edit + delete).
6. **Pages** — `/`, `/builder`, `/players`, `/tips`, `/meals`, `/admin` serve files from `static/`; assets mount at `/static`.

Frontend is plain ES modules, no build step, no external requests (works fully offline):

- `static/wim.js` — `WIM_SVG` glyph, `fmtW`/`wim` formatting, `renderNav(active)`, `api()` fetch wrapper, `toast()`, `starBar()`, `esc()` (**always escape user-supplied strings before inserting into innerHTML**), session helpers (`getSession`, `saveName`, `namePrompt(required)`, `ensureNamed()`, `identityLine()` — a read-only "Posting as `<name>`" line, no edit affordance since a name is permanent once set), `connectFeed()` (auto-reconnecting `/ws/feed` client), `initFloatingBasket()` (drag-and-drop chip mechanic: chips wander the arena via `requestAnimationFrame` on an outer `.chip-wrap`, bouncing off the arena edges and off the basket itself (an obstacle rect, not just a drop target), while the inner `.float-chip` keeps its own CSS bob animation so the two motions don't fight; dragging one chip also bumps nearby wanderers aside via a velocity impulse), and `renderBarcode()` (a deterministic, purely cosmetic bar pattern from an arbitrary string — not a real Code39/Code128 encoding, no external library or network call; used for the credit-share card).
- `static/index.html` — fetches `/api/combos`, renders floating cards, client-side sort (top/new), server-enforced one-vote ratings (`my_rating`), lazy-loaded comments with per-comment upvoting, top-comment snippet surfaced on the card, live-patched via `connectFeed()`. Combos flagged `honourable` are filtered out of the sortable grid and rendered into a separate section instead (`cardHtml()` is shared between both; click/submit delegation lives on `document` rather than the main grid so both sections' cards work identically).
- `static/builder.html` — the one basket-building page. On load, checks `GET /api/deals/today` for the caller's own entry; if today's deal is already submitted, shows a locked view instead of the basket UI. Otherwise: `initFloatingBasket()` into a `Map(meal_id -> qty)`, restored from `GET /api/basket` and autosaved (debounced) to `PUT /api/basket` after every change. A suggestions panel (with a search box, capped to 12 results by default) lists pool meals that still fit the remaining budget. Submit always posts to `/api/deals` (any total, today's Daily Deal — the server rejects a second submission that day), resets the basket immediately on success, and *additionally* posts to `/api/combos` when the total lands on exactly 3000 cents; landing under 30 with more than the cheapest item's worth of credit left pops a modal offering a cosmetic "share your card" barcode (see `renderBarcode()`). Redirects to `/` on an exact hit, `/players` otherwise.
- `static/players.html` — today's ranking (closest to 30) and all-time standings (average distance since first submission, missed days counted as W$0, current streak).
- `static/tips.html` — post a tip (identity-locked, same as everywhere else); react with any of six independent toggles, sorted by score (up minus down), live-patched via `connectFeed()`.
- `static/meals.html` — add-meal form with a large food/drink emoji picker + meal pool listing.
- `static/admin.html` — admin key kept in `sessionStorage` (`wim_admin_key`), verified via `/api/admin/verify`; five tabs (Meals / Combos / Daily Deals / Comments / Tips) with inline-editable tables (comments and tips are now edit-in-place, not delete-only). The Combos tab also has a "+ New honourable mention" panel that reuses the combo item-editor markup to create a combo from scratch.

## Workflow

- Versions follow `vMAJOR.MINOR.PATCH`; planned work lives in [ROADMAP.md](ROADMAP.md) (versioned sections with priority tables), actionable items in [TODO.md](TODO.md). Mirror significant roadmap items as GitHub issues.
- Commit style: `feat: ...` / `fix: ...` / `docs: ...` / `chore: ...`.
- When a roadmap item ships: check it off in TODO.md, mark the roadmap section, close the GitHub issue, and update README if user-facing.
