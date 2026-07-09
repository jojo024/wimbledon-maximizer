# TODO

Flat actionable checklist. Grouped by roadmap version — see [ROADMAP.md](ROADMAP.md)
for context on each item. Check items off as they ship.

## v0.2.0 — Fairness and live updates

- [x] Add `voter_id` to `ratings` with UNIQUE(combo_id, voter_id); re-rating updates (#1)
- [x] Signed session cookie + one-time display-name prompt; autofill author fields (#2)
- [x] `/ws/feed` WebSocket broadcasting combo/rating/comment events (#3)
- [x] Leaderboard patches cards live with a glow on change (#3)
- [x] Admin endpoints + UI to edit combo items, preserving the 3000-cent invariant (#4)
- [x] In-memory per-IP rate limiting on all POST endpoints (#5)

## v0.3.0 — Player leaderboard, comment quality & identity integrity

- [x] Author always server-derived from session; drop free-text author/created_by fields (#1)
- [x] Daily Deal page + `/api/deals` (one submission per day, upsert on resubmit) (#2)
- [x] Players leaderboard: today's ranking + all-time avg-distance/streak standings (#2)
- [x] Comment upvotes; sort by score; surface top comment on the card (#3)
- [x] Basket Builder chips wander the arena continuously while bobbing (#4)
- [x] W-glyph favicon on all pages (#5)
- [x] Rebrand: W$ glyph uses a horizontal strikethrough (Won/Yen-style), not a vertical dollar stroke

## v0.3.1 — Arena polish & consolidation

- [x] Move the basket to the side of the arena; wandering chips treat it as an obstacle
      (bounce off it) instead of drifting over the drop zone
- [x] Bump physics: the chip currently being dragged nudges nearby wandering chips out
      of the way (impulse to their velocity, not a full physics engine)
- [x] Consolidate Basket Builder + Daily Deal into one page (`/builder`): always logs
      today's Daily Deal, additionally posts a Combo when the total is exactly 3000
      cents; `/deals` page removed, `/api/deals/*` endpoints unchanged
- [x] Expand the emoji picker (`static/meals.html`, `EMOJIS` array) to ~120 food/drink emojis

## v0.3.2 — Internet deployment hardening

- [x] Resolve the deployment-topology risks flagged in the v0.3.1 security review:
      trust `X-Forwarded-For`/`X-Forwarded-Proto` only via uvicorn's own
      `forwarded_allow_ips` (default `127.0.0.1`) instead of a custom, riskier
      reimplementation; cookie `Secure` flag now follows the resolved scheme; added
      a global + per-IP cap on `/ws/feed` connections
- [x] Warn on startup if `WIM_ADMIN_KEY` is unset (still using the default)
- [x] Pin exact dependency versions in requirements.txt
- [x] `deploy/` — Caddyfile (reverse proxy + automatic HTTPS), systemd unit, env template
- [x] README § Deploying on the internet — VPS setup steps and the ongoing
      pull-and-restart update workflow
- [x] Display name is now permanently locked once set — `/api/session/name` 400s on
      a second call; the "change" link/flow removed from the UI entirely
- [x] Basket moved back to dead-center (the obstacle-bounce physics from v0.3.1
      already keep wandering chips clear of it; the off-to-the-side workaround
      was no longer needed)
- [x] Basket hint icon changed to the actual "basket" emoji (was a stray mango)

## v0.4.0 — Seasons and polish

- [ ] Season table + weekly rollover job; archive past seasons
- [ ] Hall of fame page for past season winners
- [ ] Winner podium (top 3) section on the leaderboard
- [ ] Optional meal photo upload (stored next to the DB, served statically)
- [ ] Bigger touch targets + drop feedback for mobile drag
- [ ] Dockerfile + docker-compose.yml

## Housekeeping

- [x] **Red-team security review** — see findings below; fixed the actionable ones
      (admin key default had regressed to "wimbledons", non-constant-time key
      comparison, no rate limiting on admin endpoints). SQL injection surface,
      XSS escaping, CORS, and CSRF all came back clean.
- [x] Deployment-topology risks from the review — resolved in v0.3.2 above.
- [ ] pytest suite: combo total validation, admin auth, snapshot integrity, cascade deletes
- [ ] GitHub Actions CI: syntax + import check on push

## Done (v0.3.2)

- [x] Internet-deployment hardening (proxy-aware IP/scheme, secure cookies, WS cap,
      startup warning, pinned deps, Caddy + systemd artifacts, permanent display names)

## Done (v0.3.1)

- [x] Arena obstacle-avoidance + bump physics, Basket Builder/Daily Deal consolidation, larger emoji picker

## Done (v0.3.0)

- [x] Identity lock-down, Daily Deal + Players leaderboard, comment upvotes, wandering chips, favicon

## Done (v0.2.0)

- [x] Server-side one-rating-per-user, session identity, live leaderboard, admin combo-item editor, rate limiting

## Done (v0.1.0)

- [x] FastAPI + SQLite backend with seed data
- [x] W$ SVG glyph (W with dollar stroke) used for all prices
- [x] Leaderboard with floating cards, star ratings, comments, top/new sort
- [x] Basket Builder: drag floating meals into basket, live 30-Wimbledons meter
- [x] Add Meals page with 48-emoji picker
- [x] Admin console: meals / combos / comments tabs, key-protected
- [x] Combo snapshot model (integer cents, exact-3000 validation)
- [x] README, CLAUDE.md, ROADMAP, TODO documentation set
