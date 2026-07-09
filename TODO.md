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

## v0.3.3 — Basket Builder usability

- [x] Suggestions panel at the bottom of the basket: pool meals that still fit within
      the remaining budget (won't push the total over 30), sorted priciest-first,
      the one that would land exactly on 30 highlighted; click one to add it straight
      to the basket, same as dragging it in
- [x] Meal price input allowed any value (was restricted to .5 increments client-side
      via `step="0.5"` — the server never had this restriction, it was frontend-only,
      affecting the add-meal form and both admin price editors)

## v0.3.4 — Tips board, persistent basket, credit sharing

- [x] Tips & Tricks board (`/tips`): post + upvote tips, sorted by score, live-updated;
      admin list/delete tab
- [x] Basket Builder draft autosaves per session (`GET`/`PUT /api/basket`, scoped to
      today), restored on load, debounced save after every change — pick up where
      you left off and submit at the end of the day
- [x] Cosmetic credit-share barcode: landing under 30 Wimbledons offers to generate a
      shareable barcode from a real card number you type in — purely visual, no
      backend storage or redemption, zero effect on scores or the leaderboard
- [x] Credit-share barcode moved into a modal popup (matching the name-prompt modal)
      instead of a panel stranded at the bottom of the page
- [x] Bigger Basket Builder arena (560px → 720px desktop, 440px → 480px mobile);
      arena's share of the layout grid widened (1.6fr → 2fr) now that the meal pool
      has grown
- [x] Search box next to "Still fits", filtering the suggestions list by meal name;
      the default (no search) list is capped to 12 so a large pool doesn't produce
      an unusably long list — the search box is how you find the rest

## v0.3.5 — Tip reactions, admin edit powers, one deal per day

- [x] Tips reactions generalized from a single upvote to six independent toggles:
      up, down, fire, heart, laugh, cry — several can be active at once on the same
      tip. Sort score is up-minus-down; the other four are flavor, not ranking
- [x] Admin can now edit (not just delete) comments and tips — inline author/text
      fields + Save, matching the existing meals/combos pattern
- [x] Daily Deal is strictly one submission per day — resubmitting the same day now
      400s ("come back tomorrow") instead of silently correcting the total; enforced
      by the `UNIQUE(voter_id, deal_date)` constraint itself (no separate check-then-
      insert race), and the client shows a locked "already submitted" view on return
- [x] Basket resets immediately after a successful submission (both client-side and
      the server-side draft) rather than leaving the just-submitted items visible

## v0.3.6 — Honourable mentions, barcode realism

- [x] Admin can create "honourable mention" combos directly (still exactly 30
      Wimbledons — the joke needs a real combination) — funky, admin-curated,
      shown in their own section on the leaderboard, never counted in the ranking
      or the top-rated sort
- [x] Credit-share barcode redrawn denser (1px gaps, 5 bar segments/char, narrow-
      dominant widths) to actually read as a barcode, per a reference photo
- [x] Credit-share popup only appears when leftover credit exceeds W$1.05 (the
      cheapest catalog item) — below that there's nothing left to "stock up" on

## v0.3.7 — Honourable-mention picker fix

- [x] Replace free-text emoji/name/price/qty entry in the admin "+ New honourable
      mention" form with a meal picker (`<select>` of the live pool + qty, copying
      emoji/name/price_cents straight from the meal record) — fixes a live 422 on
      wmax.shop caused by a blank emoji field and the clunkiness the user reported

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
- [ ] **Bug:** Basket Builder meter only reaches 50% width at exactly 30 Wimbledons
      (it visualizes up to `TARGET * 2` = 60, so a modest basket looks like it
      "stops 1/3 way through" instead of reflecting progress toward 30 directly).
      Reported with a suggested fix: rescale so the bar fills 0→100% as you
      approach 30 (not 60), keep the green-at-exact / different-color-when-over
      treatment that already exists (`.meter.exact`/`.meter.over` in style.css).
      Not yet fixed — flagged for a deliberate rescale, not a quick patch, since
      "over 30" then needs its own visual language once 30 is the top of the bar.
- [ ] pytest suite: combo total validation, admin auth, snapshot integrity, cascade deletes
- [ ] GitHub Actions CI: syntax + import check on push

## Done (v0.3.7)

- [x] Meal-picker replaces free-text entry in the honourable-mention admin form

## Done (v0.3.6)

- [x] Honourable-mention combos, denser barcode rendering, credit-share threshold

## Done (v0.3.5)

- [x] Six-reaction tips, admin edit for comments/tips, one-deal-per-day + basket reset

## Done (v0.3.4)

- [x] Tips & Tricks board, persistent per-user basket draft, cosmetic credit-share barcode

## Done (v0.3.3)

- [x] Basket-builder "still fits" suggestions, any-price meal input (not just .5 steps)

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
