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

## v0.3.0 — Seasons and polish

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Competition seasons (weekly reset + archive) | M | Keeps the game fresh; old winners preserved in a hall of fame |
| 2 | Winner podium on landing page | S | Celebrate the top combo of the season |
| 3 | Meal images (optional upload) | M | Emojis are the soul, photos are the proof |
| 4 | Mobile drag polish | S | Touch drag works but chips are small; larger hit areas + haptics |
| 5 | Docker support | S | One-command deploy on a home server |

## Backlog (unscheduled)

- Configurable target (30 Wimbledons is sacred, but a "hard mode" 50-Wimbledons bracket could be fun)
- Combo duplicate detection (same multiset of items)
- Export/import database (JSON)
- Basic pytest suite: combo validation, admin auth, snapshot integrity
- CI workflow (syntax + import check, like CCD's)
- Confetti burst when the meter hits exactly 30 Wimbledons
