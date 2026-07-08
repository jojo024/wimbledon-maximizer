# Wimbledon$ Maximizer

A locally hosted web app built around one joke: the **Wimbledon** (always plural: **Wimbledons**), a fake currency written **W$** — a letter W struck through like a dollar sign.

The game: log the meals you ate today with a price in Wimbledons and an emoji, then build a daily meal combination that costs **exactly 30 Wimbledons**. Not 29 Wimbledons. Not 31 Wimbledons. Valid combos enter the competition on the landing page, where everyone can rate them (1–5 stars) and comment.

## Features

- **Leaderboard** (`/`) — floating glassmorphic combo cards; sort by top rated or newest; star ratings (one per browser) and comments per combo.
- **Basket Builder** (`/builder`) — meals and snacks float around a shopping basket; drag them in, the total is tracked live with a meter that glows green at exactly 30 Wimbledons and unlocks competition entry.
- **Add Meals** (`/meals`) — log a meal with name, price in Wimbledons, and an emoji (48-emoji picker or type your own); it joins the shared meal pool.
- **Admin console** (`/admin`) — key-protected; edit or delete any meal, rename or delete combos, reset ratings, delete comments.
- **W$ glyph** — custom SVG (W with a vertical dollar stroke), used consistently for every price in the UI.
- Purple/green futuristic dark theme: glass cards, neon glows, grid overlay, floating animations.

## Quickstart

```bash
pip install -r requirements.txt
python main.py
# open http://localhost:8030
```

On first run `wimbledon.db` (SQLite) is created next to `main.py` and seeded with 18 meals and 2 example combos.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `WIM_ADMIN_KEY` | `wimbledon` | Key for the `/admin` console and admin API (sent as `X-Admin-Key` header) |
| `WIM_PORT` | `8030` | HTTP port |

Change the admin key before letting anyone else on the network use it.

## Tech stack

- **Backend**: Python, FastAPI, SQLite via `sqlite3` (no ORM), uvicorn. Single file: `main.py`.
- **Frontend**: plain HTML/CSS/JS ES modules, zero build step, zero external dependencies (fully offline-capable). Shared helpers in `static/wim.js`, design tokens in `static/style.css`.

## Project structure

```
main.py              FastAPI app: DB schema + seed, public API, admin API, page routes
requirements.txt     fastapi, uvicorn
static/
  style.css          design tokens (purple/green), all component styles
  wim.js             W$ SVG glyph, currency formatting, nav, fetch helper, toasts, star bars
  index.html         leaderboard: floating combo cards, rating, comments
  builder.html       drag-and-drop basket arena, 30-Wimbledons meter, competition entry
  meals.html         add-meal form with emoji picker + meal pool listing
  admin.html         admin console (meals / combos / comments tabs)
wimbledon.db         SQLite database (created at runtime, not committed)
```

## API overview

All prices are stored and transported as integer cents of a Wimbledon (`price_cents`); `3000` = exactly 30 Wimbledons.

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/meals` | GET / POST | – | List meal pool / add a meal |
| `/api/combos` | GET / POST | – | List combos with items, rating stats, comment count / submit a combo (server rejects any total that is not exactly 3000 cents) |
| `/api/combos/{id}/rate` | POST | – | Add a 1–5 star rating |
| `/api/combos/{id}/comments` | GET / POST | – | Read / add comments |
| `/api/admin/verify` | GET | `X-Admin-Key` | Check the admin key |
| `/api/admin/meals/{id}` | PUT / DELETE | `X-Admin-Key` | Edit / delete a meal |
| `/api/admin/combos/{id}` | PUT / DELETE | `X-Admin-Key` | Rename / delete a combo |
| `/api/admin/ratings/{combo_id}` | DELETE | `X-Admin-Key` | Reset a combo's ratings |
| `/api/admin/comments` | GET | `X-Admin-Key` | List all comments |
| `/api/admin/comments/{id}` | DELETE | `X-Admin-Key` | Delete a comment |

## Design decisions

- **Combo items are snapshots.** When a combo is submitted, each item's name/emoji/price is copied into `combo_items`. Admins can later edit or delete meals without corrupting historical combos — a combo that once cost 30 Wimbledons stays 30 Wimbledons forever.
- **Integer cents everywhere.** Prices are integers (`price_cents`) so the "exactly 30" check is exact — no floating-point drift.
- **One rating per browser** is enforced client-side via `localStorage` only. Server-side enforcement is a roadmap item (see [ROADMAP.md](ROADMAP.md)).
- **No user accounts** in v0.1 — names are free-text. Deliberate: zero friction for a lunch-table game.

## Development

See [CLAUDE.md](CLAUDE.md) for conventions, [ROADMAP.md](ROADMAP.md) for planned versions, and [TODO.md](TODO.md) for the actionable checklist. There is no test suite yet; validation is manual (see the smoke-test commands in CLAUDE.md).
