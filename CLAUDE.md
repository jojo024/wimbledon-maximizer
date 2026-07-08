# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

**Wimbledon$ Maximizer** — a locally hosted FastAPI + SQLite web app. Users log meals (name, emoji, price in **Wimbledons**, the fake currency) and build daily meal combos that must total **exactly 30 Wimbledons** to enter the competition on the landing page, where combos are rated and commented on. An admin console edits the whole database.

## Commands

```bash
pip install -r requirements.txt
python main.py                      # serves on http://localhost:8030
WIM_PORT=9000 python main.py        # custom port
WIM_ADMIN_KEY=secret python main.py # custom admin key (default: "wimbledon")
```

No test suite. Smoke-test after changes:

```bash
curl -s http://127.0.0.1:8030/api/meals | head -c 200
curl -s -X POST http://127.0.0.1:8030/api/combos -H "Content-Type: application/json" \
  -d '{"name":"t","author":"t","items":[{"meal_id":3,"qty":1},{"meal_id":8,"qty":1},{"meal_id":7,"qty":1},{"meal_id":2,"qty":1}]}'
# seed meal ids 3+8+7+2 = 1200+1000+500+300 cents = exactly 30 Wimbledons
curl -s http://127.0.0.1:8030/api/admin/verify -H "X-Admin-Key: wimbledon"
```

Delete `wimbledon.db` to reset to seed data.

## Hard rules

- **The currency is always plural: "Wimbledons".** Never "30 Wimbledon", never "Wimbledon dollars". That plural is the joke and it is load-bearing. UI copy, API error messages, docs — everywhere.
- **The W$ symbol** is the SVG glyph in `static/wim.js` (`WIM_SVG`): a W with a vertical stroke through it, like a dollar sign. Use `wim(cents)` for every price shown in the UI; do not hand-write "W$" strings in HTML except where a plain-text fallback is unavoidable.
- **Prices are integer cents** (`price_cents`, 3000 = 30 Wimbledons). Never store or compare floats. API request bodies take `price` as a float in Wimbledons and convert with `round(price * 100)` at the boundary.
- **Combo items are snapshots.** `combo_items` copies name/emoji/price_cents at submission time. Never join combos back to `meals` — meals are editable/deletable and combos must stay historically exact.
- **Colour scheme is purple/green futuristic dark.** All colours come from the tokens at the top of `static/style.css` (`--purple*`, `--green*`, glass tokens). Do not introduce new hex values outside the token block.
- **No emojis in docs, commit messages, or code comments.** Food emojis as app data (meal records, picker grid, seed rows) are the product and are fine.

## Architecture

Single-process FastAPI app, everything in `main.py` (~350 lines):

1. **Schema + seed** — `init_db()` creates 5 tables (`meals`, `combos`, `combo_items`, `ratings`, `comments`) and seeds 18 meals + 2 combos when `meals` is empty. SQLite file `wimbledon.db` lives next to `main.py`; connections are opened per-request via `db()` with `PRAGMA foreign_keys = ON` (cascade deletes handle ratings/comments/items when a combo is removed).
2. **Public API** — meals CRUD (create/list), combo submission (validates total == 3000 cents, 400 otherwise), ratings, comments.
3. **Admin API** — all under `/api/admin/*`, guarded by `require_admin()` comparing the `X-Admin-Key` header to `WIM_ADMIN_KEY`.
4. **Pages** — `/`, `/builder`, `/meals`, `/admin` serve files from `static/`; assets mount at `/static`.

Frontend is plain ES modules, no build step, no external requests (works fully offline):

- `static/wim.js` — `WIM_SVG` glyph, `fmtW`/`wim` formatting, `renderNav(active)` (injects the nav into `document.body`), `api(method, url, body, adminKey)` fetch wrapper (throws `Error(detail)` on non-2xx), `toast(msg, isError)`, `starBar(avg, count, interactive)`, `esc()` — **always `esc()` user-supplied strings before inserting into innerHTML**.
- `static/index.html` — fetches `/api/combos`, renders floating cards (staggered `animation-delay`), client-side sort (top/new), star rating posts once per browser (`localStorage` key `wim_rated_<id>`), lazy-loaded comments per card.
- `static/builder.html` — chips scattered on two elliptical rings around the basket; pointer-event drag (pointerdown/move/up with `setPointerCapture`); drop inside the basket rect adds to a `Map(meal_id -> qty)`; meter turns green at exactly 3000 cents and enables submit; POST `/api/combos` then redirect to `/`.
- `static/admin.html` — admin key kept in `sessionStorage` (`wim_admin_key`), verified via `/api/admin/verify`; three tabs (Meals / Combos / Comments) with inline-editable tables.

## Workflow

- Versions follow `vMAJOR.MINOR.PATCH`; planned work lives in [ROADMAP.md](ROADMAP.md) (versioned sections with priority tables), actionable items in [TODO.md](TODO.md). Mirror significant roadmap items as GitHub issues.
- Commit style: `feat: ...` / `fix: ...` / `docs: ...` / `chore: ...`.
- When a roadmap item ships: check it off in TODO.md, mark the roadmap section, close the GitHub issue, and update README if user-facing.
