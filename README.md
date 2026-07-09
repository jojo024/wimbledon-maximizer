# Wimbledon$ Maximizer

A locally hosted web app built around one joke: the **Wimbledon** (always plural: **Wimbledons**), a fake currency written **W$** — a letter W with a horizontal strikethrough, like the Won or Yen symbols rather than a dollar sign.

The game: log the meals you ate today with a price in Wimbledons and an emoji, then build a basket in one arena. Any total logs that day's Daily Deal — the **Players** leaderboard ranks everyone by who got *closest* to 30 Wimbledons, today and all-time. Land on **exactly 30 Wimbledons** — not 29, not 31 — and the same basket *also* enters the competition on the landing page, where everyone can rate it (1–5 stars) and comment.

## Features

- **Live leaderboard** (`/`) — floating glassmorphic combo cards that update in real time over a WebSocket: new combos, ratings, and comments appear with a glow, no refresh. Sort by top rated or newest. The highest-upvoted comment on each combo is surfaced right on the card.
- **Fair ratings and comments** — one vote per person, enforced server-side via a signed session cookie (not `localStorage`); re-rating updates your existing vote. Comments can be upvoted the same way, and every post's author is your session's own display name — there is no free-text author field anywhere, so nobody can post as someone else.
- **Session identity** — a lightweight signed cookie issued on first visit; the first time you try to post anything, you're prompted for a display name. Every form shows a read-only "Posting as `<name>`" line with an explicit "change" link — never an editable author box. No passwords.
- **Basket Builder** (`/builder`) — meals and snacks wander and bob around a shopping basket docked to the side of the arena (bouncing off it like a wall, so they don't drift over the drop zone); drag one in and the chip you're moving bumps nearby ones out of the way. Submitting always logs that day's Daily Deal (any total); land on exactly 30 Wimbledons and it *also* enters the competition — one basket, two possible outcomes.
- **Players** (`/players`) — today's ranking by closeness to 30 Wimbledons, plus an all-time leaderboard: average distance from 30 across every day since your first submission (a skipped day counts as W$0, the worst possible score) and your current daily streak.
- **Add Meals** (`/meals`) — log a meal with name, price in Wimbledons, and an emoji (a large food/drink picker or type your own); it joins the shared meal pool.
- **Admin console** (`/admin`) — key-protected; edit or delete any meal, rename or delete combos, **edit a combo's items** (with a live meter enforcing the exactly-30-Wimbledons rule), reset ratings, delete comments, and review/delete Daily Deal entries.
- **Rate limiting** — a per-IP token bucket on all write endpoints keeps anyone on the LAN from spamming meals, combos, deals, or comments.
- **W$ glyph** — custom SVG (W with a horizontal strikethrough), used consistently for every price in the UI and as the browser-tab favicon.
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
| `WIM_SECRET` | auto-generated | HMAC secret for signing session cookies. If unset, a random secret is generated once and persisted to `.wim_secret` (gitignored) so sessions survive restarts. |

Change the admin key before letting anyone else on the network use it.

## Tech stack

- **Backend**: Python, FastAPI, SQLite via `sqlite3` (no ORM), uvicorn, `websockets` (live feed). Single file: `main.py`. Session cookies are signed with a hand-rolled HMAC — no extra dependency.
- **Frontend**: plain HTML/CSS/JS ES modules, zero build step, zero external dependencies (fully offline-capable). Shared helpers in `static/wim.js`, design tokens in `static/style.css`.

## Project structure

```
main.py              FastAPI app: DB schema + seed, public API, admin API, WebSocket feed, page routes
requirements.txt     fastapi, uvicorn, websockets
static/
  style.css          design tokens (purple/green), all component styles
  wim.js             W$ SVG glyph, currency formatting, nav, fetch helper, toasts, star bars,
                      session/identity helpers, WebSocket feed client, shared floating-basket drag mechanic
  favicon.svg        browser-tab icon (same glyph as WIM_SVG)
  index.html         leaderboard: floating combo cards, rating, comments, comment upvotes
  builder.html       drag-and-drop basket arena; always logs a Daily Deal, also enters the
                      competition when the total is exactly 30 Wimbledons
  players.html       today's ranking + all-time standings (avg distance, streaks)
  meals.html         add-meal form with a large food/drink emoji picker + meal pool listing
  admin.html         admin console (meals / combos / daily deals / comments tabs, combo item editor)
wimbledon.db         SQLite database (created at runtime, not committed)
.wim_secret          auto-generated HMAC secret for session cookies (created at runtime, not committed)
```

## API overview

All prices are stored and transported as integer cents of a Wimbledon (`price_cents`); `3000` = exactly 30 Wimbledons.

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/session` | GET | – | Return (and, on first call, mint) the caller's session: `{voter_id, name}` |
| `/api/session/name` | POST | – | Set the caller's display name — the only place identity can change |
| `/api/meals` | GET / POST | – | List meal pool / add a meal (author is the caller's session name; requires one to be set) |
| `/api/combos` | GET / POST | – | List combos with items, rating stats, comment count, `top_comment`, and the caller's own `my_rating` / submit a combo (server rejects any total that is not exactly 3000 cents; author from session) |
| `/api/combos/{id}/rate` | POST | – | Cast or update a 1–5 star rating; one per session (`voter_id`), enforced by a UNIQUE index |
| `/api/combos/{id}/comments` | GET / POST | – | Read comments (with vote counts + the caller's own `my_vote`, sorted by score) / add a comment (author from session) |
| `/api/comments/{id}/vote` | POST | – | Toggle the caller's upvote on a comment |
| `/api/deals` | POST | – | Submit today's Daily Deal (any total; one row per caller per calendar day, upserted on resubmit) |
| `/api/deals/today` | GET | – | Today's ranking, sorted by distance from 30 Wimbledons |
| `/api/deals/leaderboard` | GET | – | All-time standings: average distance since each player's first submission (missed days count as W$0), plus current streak |
| `/ws/feed` | WebSocket | – | Live feed: broadcasts `combo_new` / `combo_update` / `combo_delete` / `rating` / `comment` / `comment_vote` / `deal` events |
| `/api/admin/verify` | GET | `X-Admin-Key` | Check the admin key |
| `/api/admin/meals/{id}` | PUT / DELETE | `X-Admin-Key` | Edit / delete a meal |
| `/api/admin/combos/{id}` | PUT / DELETE | `X-Admin-Key` | Rename / delete a combo |
| `/api/admin/combos/{id}/items` | PUT | `X-Admin-Key` | Replace a combo's item snapshot; rejects any total that is not exactly 3000 cents |
| `/api/admin/ratings/{combo_id}` | DELETE | `X-Admin-Key` | Reset a combo's ratings |
| `/api/admin/deals` | GET | `X-Admin-Key` | List all Daily Deal entries |
| `/api/admin/deals/{id}` | DELETE | `X-Admin-Key` | Delete a Daily Deal entry |
| `/api/admin/comments` | GET | `X-Admin-Key` | List all comments |
| `/api/admin/comments/{id}` | DELETE | `X-Admin-Key` | Delete a comment |

All POST endpoints are protected by an in-memory per-IP token bucket (burst 30, refill ~1 every 2s); once exhausted, requests get a 429 with a Wimbledons-themed message. Every POST that attributes content to a person (`meals`, `combos`, `comments`, `deals`) additionally requires the caller's session to have a display name set — otherwise it's a 400, not a silently-blank author.

## Design decisions

- **Combo items are snapshots.** When a combo is submitted, each item's name/emoji/price is copied into `combo_items`. Admins can later edit or delete meals without corrupting historical combos — a combo that once cost 30 Wimbledons stays 30 Wimbledons forever. The admin item editor writes new snapshot rows directly; it never joins back to `meals`.
- **Integer cents everywhere.** Prices are integers (`price_cents`) so the "exactly 30" check is exact — no floating-point drift.
- **One rating per person, enforced server-side.** A signed HMAC cookie (`voter_id`) identifies the caller; `ratings` has a `UNIQUE(combo_id, voter_id)` index, so re-rating updates the existing row via `ON CONFLICT ... DO UPDATE` instead of creating a duplicate.
- **No passwords, ever.** Session identity is just an anonymous signed cookie plus a display name — enough to attribute posts without any account system.
- **Live updates are additive, not authoritative.** The WebSocket feed only patches an already-loaded leaderboard (with a glow to draw the eye); a fresh page load always re-fetches `/api/combos` as the source of truth, so a missed or dropped WS message can't leave the UI in a wrong state.
- **Author is never a form field.** Every write endpoint derives the author from the session's display name server-side; request models have no `author`/`created_by` field to spoof. The name can only be changed through the one dedicated endpoint (`/api/session/name`), which the UI exposes as a deliberate "change" action, never as something bundled into a post.
- **A missed Daily Deal day is scored as W$0, not skipped.** The all-time Players leaderboard is an average distance-from-30 since a player's *first* submission — every day since then, submitted or not, counts toward that average. This is what makes the streak counter meaningful: showing up daily is worth more than one great day followed by silence.
- **One basket, two outcomes, not two pages.** Basket Builder and Daily Deal used to be separate pages that scattered the same meal pool into the same arena and differed only in submit-time validation. They're merged: submitting always logs a Daily Deal (any total), and additionally posts a competition Combo when the total lands on exactly 3000 cents — instead of asking the user to pick the "right" page before they've even built anything.

## Development

See [CLAUDE.md](CLAUDE.md) for conventions, [ROADMAP.md](ROADMAP.md) for planned versions, and [TODO.md](TODO.md) for the actionable checklist. There is no test suite yet; validation is manual (see the smoke-test commands in CLAUDE.md).
