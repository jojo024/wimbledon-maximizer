# Wimbledon$ Maximizer

A locally hosted web app built around one joke: the **Wimbledon** (always plural: **Wimbledons**), a fake currency written **W$** — a letter W with a horizontal strikethrough, like the Won or Yen symbols rather than a dollar sign.

The game: log the meals you ate today with a price in Wimbledons and an emoji, then build a basket in one arena. Any total logs that day's Daily Deal — the **Players** leaderboard ranks everyone by who got *closest* to 30 Wimbledons, today and all-time. Land on **exactly 30 Wimbledons** — not 29, not 31 — and the same basket *also* enters the competition on the landing page, where everyone can rate it (1–5 stars) and comment.

## Features

- **Live leaderboard** (`/`) — floating glassmorphic combo cards that update in real time over a WebSocket: new combos, ratings, and comments appear with a glow, no refresh. Sort by top rated or newest. The highest-upvoted comment on each combo is surfaced right on the card. A separate **Honourable Mentions** section holds admin-curated, deliberately funky 30-Wimbledon combos — visible and rateable, but never part of the competitive ranking.
- **Fair ratings and comments** — one vote per person, enforced server-side via a signed session cookie (not `localStorage`); re-rating updates your existing vote. Comments can be upvoted the same way, and every post's author is your session's own display name — there is no free-text author field anywhere, so nobody can post as someone else.
- **Session identity** — a lightweight signed cookie issued on first visit; the first time you try to post anything, you're prompted for a display name. Every form shows a read-only "Posting as `<name>`" line — never an editable author box, and the name can't be changed once set, so it's a stable identity across everything you post.
- **Basket Builder** (`/builder`) — meals and snacks wander and bob around a shopping basket in the middle of the arena, bouncing off it like a wall so they don't drift over the drop zone; drag one in and the chip you're moving bumps nearby ones out of the way. Your in-progress basket autosaves per session, so you can add to it throughout the day and submit whenever you're ready — closing the tab doesn't lose it. A suggestions panel (with a search box) lists pool meals that still fit your remaining budget; click one to add it straight in. Submitting always logs that day's Daily Deal (any total, **one submission per day** — come back tomorrow for another); land on exactly 30 Wimbledons and it *also* enters the competition — one basket, two possible outcomes. Land under 30 with more than the cheapest item's worth of credit left, and a popup offers to generate a fun, shareable barcode for it.
- **Players** (`/players`) — today's ranking by closeness to 30 Wimbledons, plus an all-time leaderboard: average distance from 30 across every day since your first submission (a skipped day counts as W$0, the worst possible score) and your current daily streak.
- **Tips & Tricks** (`/tips`) — post advice on maximizing your Wimbledons; react to others' tips with six independent toggles (👍👎🔥❤️😂😢) — several can be active on the same tip at once. Ranked by score (👍 minus 👎); the rest are flavor. Live-updated for everyone watching.
- **Add Meals** (`/meals`) — log a meal with name, any price in Wimbledons, and an emoji (a large food/drink picker or type your own); it joins the shared meal pool.
- **Admin console** (`/admin`) — key-protected; edit or delete any meal, rename or delete combos, **edit a combo's items** (with a live meter enforcing the exactly-30-Wimbledons rule), **create honourable-mention combos** directly, edit or delete comments and tips, reset ratings, and review/delete Daily Deal entries.
- **Rate limiting** — a per-IP token bucket on all write endpoints (including every admin endpoint) keeps anyone from spamming meals, combos, deals, or comments, or brute-forcing the admin key.
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
| `WIM_HOST` | `0.0.0.0` | Interface uvicorn binds to. Set to `127.0.0.1` when running behind a reverse proxy (see [Deploying on the internet](#deploying-on-the-internet)) so only the proxy can reach it. |
| `WIM_PORT` | `8030` | HTTP port |
| `WIM_SECRET` | auto-generated | HMAC secret for signing session cookies. If unset, a random secret is generated once and persisted to `.wim_secret` (gitignored) so sessions survive restarts. |
| `WIM_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Passed straight to uvicorn's `forwarded_allow_ips`: only connections from these addresses have their `X-Forwarded-For`/`X-Forwarded-Proto` headers trusted for the real client IP/scheme (used by rate limiting and the cookie's `Secure` flag). The default matches the documented `WIM_HOST=127.0.0.1`-behind-Caddy setup; leave it alone unless your reverse proxy runs somewhere else. |

Change the admin key before letting anyone else reach this — on a LAN or the internet.

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
  index.html         leaderboard: floating combo cards, rating, comments, comment upvotes,
                      plus a separate Honourable Mentions section (admin-curated, unranked)
  builder.html       drag-and-drop basket arena, autosaved per-user draft, "still fits"
                      suggestions with search; one Daily Deal submission per day, also
                      enters the competition when the total is exactly 30 Wimbledons;
                      cosmetic credit-share barcode (modal) when there's credit left over
  players.html       today's ranking + all-time standings (avg distance, streaks)
  tips.html          post tips, react with up/down/fire/heart/laugh/cry, sorted by score,
                      live-updated
  meals.html         add-meal form with a large food/drink emoji picker + meal pool listing
  admin.html         admin console (meals / combos / daily deals / comments / tips tabs,
                      combo item editor, honourable-mention combo creator)
wimbledon.db         SQLite database (created at runtime, not committed)
.wim_secret          auto-generated HMAC secret for session cookies (created at runtime, not committed)
deploy/
  Caddyfile                          reverse proxy + automatic HTTPS config
  wimbledon-maximizer.service        systemd unit (Restart=on-failure)
  wimbledon-maximizer.env.example    template for the real env file (gitignored)
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
| `/api/deals` | POST | – | Submit today's Daily Deal (any total). **One submission per calendar day** — a second attempt the same day gets a 400, not a silent correction. Clears the caller's basket draft on success. |
| `/api/deals/today` | GET | – | Today's ranking, sorted by distance from 30 Wimbledons; includes `mine: true` on the caller's own entry, if any |
| `/api/deals/leaderboard` | GET | – | All-time standings: average distance since each player's first submission (missed days count as W$0), plus current streak |
| `/api/basket` | GET / PUT | – | Read / replace the caller's in-progress Basket Builder draft for today (autosave, not a submission — no display name required) |
| `/api/tips` | GET / POST | – | List tips with per-reaction counts, `score` (👍 minus 👎), and the caller's own `my_reactions`, sorted by score / post a tip (author from session) |
| `/api/tips/{id}/react` | POST | – | Toggle one of six reactions (`up`/`down`/`fire`/`heart`/`laugh`/`cry`) on a tip; several can be active at once from the same caller |
| `/ws/feed` | WebSocket | – | Live feed: broadcasts `combo_new` / `combo_update` / `combo_delete` / `rating` / `comment` / `comment_vote` / `deal` / `tip_new` / `tip_react` / `tip_update` / `tip_delete` events |
| `/api/admin/verify` | GET | `X-Admin-Key` | Check the admin key |
| `/api/admin/meals/{id}` | PUT / DELETE | `X-Admin-Key` | Edit / delete a meal |
| `/api/admin/combos` | POST | `X-Admin-Key` | Create an "honourable mention" combo directly (still must total exactly 3000 cents) — shown on the leaderboard, excluded from the competitive ranking |
| `/api/admin/combos/{id}` | PUT / DELETE | `X-Admin-Key` | Rename / delete a combo |
| `/api/admin/combos/{id}/items` | PUT | `X-Admin-Key` | Replace a combo's item snapshot; rejects any total that is not exactly 3000 cents |
| `/api/admin/ratings/{combo_id}` | DELETE | `X-Admin-Key` | Reset a combo's ratings |
| `/api/admin/deals` | GET | `X-Admin-Key` | List all Daily Deal entries |
| `/api/admin/deals/{id}` | DELETE | `X-Admin-Key` | Delete a Daily Deal entry |
| `/api/admin/comments` | GET | `X-Admin-Key` | List all comments |
| `/api/admin/comments/{id}` | PUT / DELETE | `X-Admin-Key` | Edit / delete a comment (author and text) |
| `/api/admin/tips` | GET | `X-Admin-Key` | List all tips, with per-reaction score and total reaction count |
| `/api/admin/tips/{id}` | PUT / DELETE | `X-Admin-Key` | Edit / delete a tip (author and text) |

All POST endpoints are protected by an in-memory per-IP token bucket (burst 30, refill ~1 every 2s); once exhausted, requests get a 429 with a Wimbledons-themed message. Every POST that attributes content to a person (`meals`, `combos`, `comments`, `deals`, `tips`) additionally requires the caller's session to have a display name set — otherwise it's a 400, not a silently-blank author. The basket-draft endpoints are the one exception: browsing/building doesn't require a name, only submitting does.

## Design decisions

- **Combo items are snapshots.** When a combo is submitted, each item's name/emoji/price is copied into `combo_items`. Admins can later edit or delete meals without corrupting historical combos — a combo that once cost 30 Wimbledons stays 30 Wimbledons forever. The admin item editor writes new snapshot rows directly; it never joins back to `meals`.
- **Integer cents everywhere.** Prices are integers (`price_cents`) so the "exactly 30" check is exact — no floating-point drift.
- **One rating per person, enforced server-side.** A signed HMAC cookie (`voter_id`) identifies the caller; `ratings` has a `UNIQUE(combo_id, voter_id)` index, so re-rating updates the existing row via `ON CONFLICT ... DO UPDATE` instead of creating a duplicate.
- **No passwords, ever.** Session identity is just an anonymous signed cookie plus a display name — enough to attribute posts without any account system.
- **Live updates are additive, not authoritative.** The WebSocket feed only patches an already-loaded leaderboard (with a glow to draw the eye); a fresh page load always re-fetches `/api/combos` as the source of truth, so a missed or dropped WS message can't leave the UI in a wrong state.
- **Author is never a form field, and a name is permanent once set.** Every write endpoint derives the author from the session's display name server-side; request models have no `author`/`created_by` field to spoof. `/api/session/name` only succeeds once per session — the server rejects a second call — so there's no client-side "change identity" flow to build or secure.
- **A missed Daily Deal day is scored as W$0, not skipped.** The all-time Players leaderboard is an average distance-from-30 since a player's *first* submission — every day since then, submitted or not, counts toward that average. This is what makes the streak counter meaningful: showing up daily is worth more than one great day followed by silence.
- **One basket, two outcomes, not two pages.** Basket Builder and Daily Deal used to be separate pages that scattered the same meal pool into the same arena and differed only in submit-time validation. They're merged: submitting always logs a Daily Deal (any total), and additionally posts a competition Combo when the total lands on exactly 3000 cents — instead of asking the user to pick the "right" page before they've even built anything.
- **The credit-share barcode is deliberately cosmetic.** `renderBarcode()` draws a deterministic bar pattern from whatever string you type — it is *not* a real Code39/Code128 encoding, isn't validated or stored server-side, and redeeming it (there's nothing to redeem) has zero effect on anyone's total or the leaderboard. It exists purely so you can screenshot and share it; building an actual credit-transfer mechanic would let people game their own closeness-to-30 score with someone else's leftover balance, which would cheapen the entire competition. It only appears when there's more left than the cheapest catalog item — otherwise there's nothing to meaningfully "stock up" on.
- **The basket draft is scoped to `(voter_id, today)`, not just `voter_id`.** It autosaves your in-progress Basket Builder so you can leave and come back, but it isn't meant to accumulate indefinitely — a new calendar day starts you with an empty basket, matching the Daily Deal it's building toward.
- **A Daily Deal submission is final, not a draft you can correct.** Unlike the basket (which autosaves freely until you submit), `POST /api/deals` succeeds exactly once per `(voter_id, deal_date)` — the database's own `UNIQUE` constraint is what enforces this, not an application-level check, so there's no race between two tabs submitting at once. This was a deliberate tightening: an earlier version allowed resubmitting to "correct" the total, which undercut the point of showing up daily.
- **Reactions carry a signal; not all of them count.** Tips have six independent reaction toggles, but only up/down feed the sort `score` — fire/heart/laugh/cry are expressive, not competitive. Combos follow the same philosophy at a coarser grain: **honourable mentions** are real, valid, exactly-30-Wimbledon combos that are simply excluded from the ranking by an admin-set flag, so the leaderboard's "top rated" list stays a genuine ranking of player-submitted combos even as the app makes room for admin-curated fun.

## Deploying on the internet

This assumes a Linux VPS (IONOS, Hostinger, DigitalOcean, etc. — the steps below are
the same regardless of provider once you have root SSH access) and a domain whose DNS
you control. The app itself never talks TLS — Caddy sits in front of it, terminates
HTTPS with an automatically-provisioned Let's Encrypt certificate, and proxies
everything (including the `/ws/feed` WebSocket) to uvicorn, which only listens on
`127.0.0.1` so it's unreachable except through Caddy.

**One-time setup, on the server:**

```bash
# 1. DNS: create an A record for your domain pointing at the VPS's public IP
#    (do this first — Caddy needs it resolvable to issue a certificate).

# 2. System packages
sudo apt update && sudo apt install -y python3-venv caddy

# 3. Get the code
sudo mkdir -p /opt/wimbledon-maximizer
sudo chown $USER /opt/wimbledon-maximizer
git clone https://github.com/<you>/wimbledon-maximizer.git /opt/wimbledon-maximizer
cd /opt/wimbledon-maximizer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Configure secrets
cp deploy/wimbledon-maximizer.env.example deploy/wimbledon-maximizer.env
nano deploy/wimbledon-maximizer.env   # set a real WIM_ADMIN_KEY

# 5. Run it as a service
sudo useradd -r -s /usr/sbin/nologin wimbledon || true
sudo chown -R wimbledon:wimbledon /opt/wimbledon-maximizer
sudo cp deploy/wimbledon-maximizer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wimbledon-maximizer

# 6. Reverse proxy + HTTPS
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile        # put your real domain in place of the placeholder
sudo systemctl reload caddy

# 7. Firewall: only 80/443 need to be reachable from the internet (uvicorn's
#    8030 is bound to loopback already, but belt-and-suspenders):
sudo ufw allow 80,443/tcp
sudo ufw enable
```

Visit `https://your-domain` — Caddy fetches the certificate on first request.

**Ongoing workflow — adding features and fixing bugs:**

There's no build step and no separate "staging" environment for a project this size,
so the loop is short:

1. Develop and test locally exactly as described in [Quickstart](#quickstart) —
   `python main.py`, hit `http://localhost:8030`, iterate.
2. Commit and push to `main` once it works locally.
3. On the server: `cd /opt/wimbledon-maximizer && git pull && sudo systemctl restart wimbledon-maximizer`.

That's the whole deploy: pull the new code, restart the process. `init_db()` runs
every startup and only ever *adds* tables/columns (`CREATE TABLE IF NOT EXISTS`,
guarded `ALTER TABLE ... ADD COLUMN`), so a schema change ships the same way as a
one-line copy fix — no separate migration step, and the live `wimbledon.db` is
never dropped or recreated by a restart.

A few habits worth keeping as this grows:
- `sudo journalctl -u wimbledon-maximizer -f` to watch logs / catch the startup
  warning if `WIM_ADMIN_KEY` is ever accidentally unset.
- Before a change that touches the DB schema, `cp wimbledon.db wimbledon.db.bak`
  on the server as a cheap rollback point.
- If a deploy breaks something, `git log --oneline`, find the last good commit,
  `git checkout <sha>` (or `git revert`), restart the service.
- The Housekeeping section of [TODO.md](TODO.md) has the next real investments here
  — a pytest suite and GitHub Actions CI — worth doing once bugs start slipping
  through manual smoke-testing.

## Development

See [CLAUDE.md](CLAUDE.md) for conventions, [ROADMAP.md](ROADMAP.md) for planned versions, and [TODO.md](TODO.md) for the actionable checklist. There is no test suite yet; validation is manual (see the smoke-test commands in CLAUDE.md).
