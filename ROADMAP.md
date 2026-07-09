# Roadmap

Planned work, grouped by version. Each item: title, affected files, problem, proposed fix.
Workflow: items here are mirrored as GitHub issues; when shipped, the section gets a
`> Status:` footer and the issues are closed. See [TODO.md](TODO.md) for the flat checklist.

## v0.1.0 — Initial release

Core game: meal pool, 30-Wimbledons basket builder, competition leaderboard with
ratings and comments, admin console, W$ glyph, purple/green futuristic theme.

> **Status:** Shipped. This is the current version.

## v0.2.0 — Fairness and live updates

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Server-side one-rating-per-user | M | Ratings drive the competition; localStorage is trivially bypassed |
| 2 | Session identity (pick-a-name once) | M | Prereq for item 1; also autofills author fields |
| 3 | Live leaderboard via WebSocket | M | New combos/ratings should appear without refresh — fits the futuristic feel |
| 4 | Admin: edit combo items | S | Admin can rename combos but not fix a wrong item; "edit everything" isn't complete |
| 5 | Rate limiting on write endpoints | S | Anyone on the LAN can spam meals/comments |

### Item details

1. **Server-side one-rating-per-user** — `main.py`. Ratings table gains a `voter_id`
   column with a UNIQUE(combo_id, voter_id) constraint; re-rating updates the existing
   row. Voter id comes from the session cookie (item 2).
2. **Session identity** — `main.py`, `static/wim.js`. Lightweight signed cookie
   (itsdangerous or hand-rolled HMAC) issued on first visit; a "who are you?" prompt
   stores a display name against it. No passwords.
3. **Live leaderboard** — `main.py`, `static/index.html`. `/ws/feed` broadcasts
   combo/rating/comment events; leaderboard patches cards in place with a glow
   animation on change.
4. **Admin combo item editor** — `main.py`, `static/admin.html`. New admin endpoints
   to add/remove/requantify `combo_items` rows; keep the exactly-3000-cents invariant
   or flag the combo as invalid.
5. **Rate limiting** — `main.py`. Simple in-memory token bucket per client IP on
   POST endpoints; 429 with a friendly Wimbledons-themed message.

> **Status:** Shipped.

## v0.3.0 — Player leaderboard, comment quality & identity integrity

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Identity lock-down: author always server-derived from session | S | v0.2.0 added session identity but forms still let you type any name at post time — trivially spoofable |
| 2 | Daily Deal + Players leaderboard | M | A second game mode: log any real daily total (not exactly 30) and rank players by closeness to 30, all-time |
| 3 | Comment upvotes + "top comment" surfaced on the card | S | Best commentary should be visible on the leaderboard, not buried in a click-to-open panel |
| 4 | Basket Builder chips wander continuously, not just bob in place | XS | The float animation was static-position; a little chaos makes drag-and-drop more fun |
| 5 | W-glyph favicon | XS | Every other surface uses the glyph; the browser tab didn't |
| 6 | Rebrand: horizontal-strikethrough glyph | XS | Vertical dollar-stroke read as generic currency; a horizontal strike (Won/Yen-style) is more distinctive and still reads as a struck-through W |

### Item details

1. **Identity lock-down** — `main.py`, all four page scripts. `MealIn`/`ComboIn`/`CommentIn`
   drop their free-text `author`/`created_by` fields entirely; every write endpoint derives
   the author from the session's `display_name` via `require_named()`, which 400s if no
   name is set yet. Forms show a read-only "Posting as `<name>` · change" line instead of
   an editable box; changing your handle is a deliberate, separate action, never bundled
   into a post.
2. **Daily Deal / Players** — `main.py`, `static/deals.html`, `static/players.html`.
   `daily_deals`/`daily_deal_items` tables, one row per `(voter_id, deal_date)` (upsert on
   resubmit, same day only). `/api/deals/today` ranks today's submissions by distance from
   30 Wimbledons; `/api/deals/leaderboard` computes each player's all-time average distance
   since their first submission, counting any skipped day as W$0 spent (max distance), plus
   a current streak. Rewards showing up every day, not just spending a lot once.
3. **Comment upvotes** — `main.py`, `static/index.html`. `comment_votes` table
   (one toggleable upvote per session per comment); comments sort by score; the
   highest-voted comment for a combo (if any) is surfaced directly on the card via
   `top_comment`, live-patched over `/ws/feed`.
4. **Wandering chips** — `static/wim.js` (`initFloatingBasket`), `static/style.css`.
   Chips live in a `.chip-wrap` that a `requestAnimationFrame` loop drifts around the arena
   (bouncing off the edges) while the inner `.float-chip` keeps its own CSS bob animation —
   two independent motions on nested elements so their `transform`s don't fight, and dragging
   pauses just the one chip being moved.
5. **Favicon** — `static/favicon.svg`, all `<head>`s. Same path data as `WIM_SVG`.
6. **Rebrand** — `static/wim.js`, `static/favicon.svg`. `WIM_SVG`'s second path changed
   from a vertical stroke (`M12 2.5 V21.5`, dollar-sign style) to a horizontal one
   (`M2 12 H22`, Won/Yen style). The W zigzag itself is unchanged. "Wimbledon$" (with a
   literal dollar sign) remains correct in prose and headings — only the glyph's stroke
   orientation changed.

> **Status:** Shipped.

## v0.3.1 — Arena polish & consolidation

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Move the basket to the side of the arena | XS | Wandering chips drifted across the drop zone and visually blocked it |
| 2 | Wandering chips treat the basket as an obstacle | S | Repositioning alone doesn't stop chips drifting back over it; needs a bounce rule, not just a new resting position |
| 3 | Bump physics while dragging | S | The chip under your cursor nudges others out of the way — fun, and reinforces that the arena is "alive" |
| 4 | Expand the emoji picker | XS | 48 curated emojis was a small slice of the Unicode food/drink block |
| 5 | Consolidate Basket Builder + Daily Deal into one page | M | They were the same drag-a-basket interaction; only the submit-time validation differed |

### Item details

1–2. **Basket as an obstacle** — `static/style.css` (`.basket` now docks at `left: 80%`
   instead of dead-center), `static/wim.js` (`initFloatingBasket`). Wanderers bounce off
   the basket's bounding box each tick (closest-edge push-out, same technique as the
   arena-wall bounce) instead of drifting across it.
3. **Bump physics** — `static/wim.js` (`initFloatingBasket`). While dragging, every
   wanderer within a radius of the dragged chip's live position gets a velocity impulse
   away from it (proportional to closeness, capped at a max speed); the existing tick
   loop carries the nudge forward, so no separate render path was needed.
4. **Emoji picker** — `static/meals.html` (`EMOJIS`). Expanded from 48 to ~120 covering
   fruit, vegetables, bakery, dairy, meat/protein, rice/noodles/soups, sweets, drinks,
   and utensils — the practical food/drink emoji set, skipping live-animal emojis.
5. **Consolidation** — `static/builder.html` (merged), `static/deals.html` (removed),
   `main.py` (`/deals` page route removed; `/api/deals/*` endpoints unchanged). One
   arena, one submit action: it always upserts today's Daily Deal (any total) and
   additionally posts a named Combo to the competition when the total is exactly 3000
   cents. Nav drops the separate "Daily Deal" link; `/players` links back to `/builder`.

> **Status:** Shipped.

## v0.4.0 — Seasons and polish

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Competition seasons (weekly reset + archive) | M | Keeps the game fresh; old winners preserved in a hall of fame |
| 2 | Winner podium on landing page | S | Celebrate the top combo of the season |
| 3 | Meal images (optional upload) | M | Emojis are the soul, photos are the proof |
| 4 | Mobile drag polish | S | Touch drag works but chips are small; larger hit areas + haptics |
| 5 | Docker support | S | One-command deploy on a home server |

## Security review (2026-07-09)

A red-team pass over the whole app, ahead of any deployment beyond a trusted LAN.

**Fixed on the spot** (unambiguous, no design tradeoff):
- The default admin key had regressed from `"wimbledon"` to `"wimbledons"` in an
  unrelated commit — every doc still says `"wimbledon"`, so this would have locked
  out anyone relying on the documented default. Reverted.
- `require_admin()` compared the key with a plain `!=` (a timing side-channel);
  switched to `hmac.compare_digest`, matching the session-cookie signature check.
- No `/api/admin/*` endpoint was rate-limited, so the key could be brute-forced with
  unlimited attempts/second. Added the same per-IP token bucket used elsewhere.

**Came back clean:**
- SQL injection — every query is parameterized (`?` placeholders); none build SQL
  from string interpolation.
- XSS — every user-supplied string (meal name/emoji, combo/author names, comments,
  display names) goes through `esc()` before landing in `innerHTML`; verified across
  all five pages including the just-rewritten `builder.html`.
- CSRF — no CSRF tokens exist, but none are needed: the session cookie is
  `SameSite=Lax`, which browsers don't attach to cross-site POST requests.
- CORS — no `CORSMiddleware` is configured, so the browser's same-origin policy
  applies by default; nothing loosens it.
- Session forgery — HMAC-signed `voter_id`, checked with `hmac.compare_digest`,
  128 bits of randomness per id. Not forgeable without the secret.

**Deployment-topology risks, flagged but not fixed** (each depends on how/where this
gets deployed, not something to silently change): `rate_limit()` trusts
`request.client.host`, which collapses to one shared bucket for everyone behind a
reverse proxy unless it's configured to forward the real client IP; the session
cookie has no `secure` flag (fine on plain-HTTP LAN, wrong if ever put behind HTTPS
without setting it); `/ws/feed` has no per-IP connection cap; and the app binds
`0.0.0.0` by design (LAN play), which combined with a guessable default admin key
means changing `WIM_ADMIN_KEY` before exposing this beyond a trusted LAN is
load-bearing, not optional. Tracked in [TODO.md](TODO.md).

**Verdict:** ready for its intended use case — a locally hosted game among a trusted
group on a LAN, with the admin key changed from the default. Not hardened for
unauthenticated exposure to the open internet without addressing the topology risks
above first.

## Backlog (unscheduled)

- Configurable target (30 Wimbledons is sacred, but a "hard mode" 50-Wimbledons bracket could be fun)
- Combo duplicate detection (same multiset of items)
- Export/import database (JSON)
- Basic pytest suite: combo validation, admin auth, snapshot integrity
- CI workflow (syntax + import check, like CCD's)
- Confetti burst when the meter hits exactly 30 Wimbledons
