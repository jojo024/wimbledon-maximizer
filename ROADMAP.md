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

## v0.3.2 — Internet deployment hardening

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Resolve the v0.3.1 security review's deployment-topology findings | M | User wants to deploy on the internet (IONOS VPS + domain); those findings become live risks the moment this leaves a LAN |
| 2 | Caddy reverse-proxy config + systemd service | S | Needed to actually run this on a VPS: TLS termination and process supervision |
| 3 | README deployment + update-workflow docs | S | "How do we add features/fix bugs after this is live" needed a concrete answer |
| 4 | Display name permanently locked, no "change" flow at all | XS | Tightens the v0.3.0 identity lock-down further — a name shouldn't be changeable even via its one dedicated endpoint, once set |
| 5 | Basket back to dead-center; basket hint emoji fixed | XS | The v0.3.1 physics work makes the "dock to the side" workaround unnecessary; the hint icon was a stray mango, not a basket |

### Item details

1. **Deployment-topology fixes** — `main.py`. First attempt reimplemented
   `X-Forwarded-For`/`X-Forwarded-Proto` parsing behind a custom `WIM_TRUST_PROXY` flag
   — testing surfaced two problems: uvicorn's own `ProxyHeadersMiddleware` was *already*
   doing this (enabled by default, trusting `127.0.0.1`), making the custom flag
   redundant, and the custom parser took the first entry of a comma-separated
   `X-Forwarded-For` chain instead of the last — the wrong end, and exactly the kind of
   bug that lets a client's own spoofed value survive through a real proxy. Removed the
   custom logic entirely; `client_ip()`/`is_https()` now just read `request.client`/
   `request.url.scheme` directly, since uvicorn has already resolved them correctly by
   the time application code runs. The trust boundary is uvicorn's own
   `forwarded_allow_ips` (`WIM_FORWARDED_ALLOW_IPS` env var, default `127.0.0.1`) —
   one implementation instead of two. Also added: a global (500) + per-IP (8) cap on
   `/ws/feed` connections; a startup warning (flushed explicitly — plain `print()`
   can sit in a stdout buffer indefinitely under uvicorn's event loop) when
   `WIM_ADMIN_KEY` is left at its default; exact-pinned dependency versions.
2. **Caddy + systemd** — new `deploy/` directory: `Caddyfile` (reverse proxy, automatic
   Let's Encrypt TLS, transparent WebSocket upgrade), `wimbledon-maximizer.service`
   (systemd unit, `Restart=on-failure`, sandboxed to the app directory), and
   `wimbledon-maximizer.env.example` (real secrets live in the gitignored
   `.env` copy, not the example).
3. **Deployment docs** — README § Deploying on the internet: one-time VPS setup, and
   the ongoing workflow (`git pull && systemctl restart` — `init_db()` runs every
   startup and only ever adds tables/columns, so a schema change ships the same way
   as a one-line fix, no separate migration step).
4. **Permanent names** — `main.py` (`set_session_name` 400s if a name is already set),
   `static/wim.js` (`identityLine()` dropped its "change" button; `wireIdentityChange()`
   removed entirely), and the three pages that called it.
5. **Arena tweaks** — `static/style.css` (`.basket` back to `left: 50%`), `static/wim.js`
   (scatter rings back to centering on the arena midpoint), `static/builder.html`
   (hint icon `&#129530;`, the actual 🧺 basket emoji).

> **Status:** Shipped.

## v0.3.3 — Basket Builder usability

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | "Still fits" suggestions panel | S | Building toward exactly 30 by trial-and-error dragging was tedious; surface what's actually still possible |
| 2 | Meal prices accept any value | XS | The add-meal/admin price inputs had `step="0.5"`, a client-side artifact the server never required |

### Item details

1. **Suggestions** — `static/builder.html` (`renderSuggestions`). Pool meals priced at
   or under the remaining budget, sorted priciest-first so the "best" completions
   surface first; the one that lands exactly on 30 gets a highlighted "perfect" state.
   Clicking a suggestion calls the same `addToBasket()` path as a drag-drop.
2. **Any-price meals** — `static/meals.html`, `static/admin.html`: `step="0.5"` →
   `step="0.01"` on all three price inputs (add-meal form, admin meal row, admin combo
   item editor). `MealIn.price` already accepted any float server-side — this was
   purely a frontend restriction nobody asked for.

> **Status:** Shipped.

## v0.3.4 — Tips board, persistent basket, credit sharing

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Tips & Tricks board | M | Users want to share advice on maximizing Wimbledons, with the best tips surfaced by community upvote — same pattern as comment voting |
| 2 | Basket Builder draft autosaves per user | M | Building a basket throughout the day (adding meals as you eat them) shouldn't be lost by closing the tab; submit at day's end |
| 3 | Cosmetic credit-share barcode | S | Landing under 30 leaves "credit on the card"; a fun, shareable barcode for it — deliberately not a functional transfer, to protect leaderboard integrity |

### Item details

1. **Tips board** — `main.py` (`tips`/`tip_votes` tables, `GET`/`POST /api/tips`,
   `POST /api/tips/{id}/vote`, admin list/delete), `static/tips.html` (new page,
   reuses the `.comment`/`.cvote` styling from comment voting rather than introducing
   parallel CSS), `static/wim.js` (nav link). Same identity rules as everywhere else:
   author from session, one upvote per person, live-patched over `/ws/feed`
   (`tip_new`/`tip_vote`).
2. **Basket draft** — `main.py` (`basket_drafts` table, keyed `(voter_id, basket_date,
   meal_id)`; `GET`/`PUT /api/basket` scoped to today), `static/builder.html` (restores
   the draft into the basket `Map` on load, autosaves debounced 500ms after every
   change). Unlike `combo_items`/`daily_deal_items`, this isn't a historical snapshot —
   it references live `meal_id`s and is meant to always reflect the current pool, since
   it's a draft of something not yet finalized.
3. **Credit-share barcode** — `static/wim.js` (`renderBarcode()`: a deterministic bar
   pattern derived from the input string's char codes, not a real Code39/Code128
   encoding), `static/builder.html` (shown instead of the immediate redirect when a
   Daily Deal lands under 30; a "Continue to Players" link replaces the auto-redirect).
   Explicitly not wired to any backend — no storage, no redemption, no effect on
   scores, by design (see Design decisions in README).

> **Status:** Shipped.

## v0.3.5 — Tip reactions, admin edit powers, one deal per day

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Generalize tip upvotes into six reactions | M | User request: downvote plus fire/heart/laugh/cry — a richer, funnier signal than a single upvote |
| 2 | Admin can edit comments and tips, not just delete | S | "Admin edits the whole database" was incomplete — comments/tips were delete-only |
| 3 | Daily Deal becomes strictly one submission per day | S | Resubmitting to "correct" a deal undermined the streak/showing-up incentive; the user wanted a hard stop with a clear warning instead |
| 4 | Basket resets immediately after submitting | XS | Companion to #3 — once submission is one-shot, leaving the just-submitted items visible in the basket is misleading |

### Item details

1. **Reactions** — `main.py`. `tip_votes` (single upvote) replaced by `tip_reactions`
   (`tip_id, voter_id, reaction` with a `CHECK` constraint on six values), migrated
   idempotently from any existing `tip_votes` rows as `'up'`. Each reaction toggles
   independently — a tip can be simultaneously 🔥'd and ❤️'d by the same person.
   Sort score is `up - down`; the other four don't affect ranking, matching the
   "reactions vs. ranking signal" split real platforms use. `static/tips.html` gets
   a six-button reaction bar per tip (reusing `.comment`/`.ctext`/`.cauthor`, adding
   `.reactions`/`.react-btn`).
2. **Admin edit** — `main.py` (`AdminTextUpdate` model, `PUT /api/admin/comments/{id}`,
   `PUT /api/admin/tips/{id}`), `static/admin.html` (author/text become inline inputs
   + a Save button, matching the meals/combos tables).
3. **One deal per day** — `main.py` (`submit_deal` drops the `ON CONFLICT DO UPDATE`
   upsert; the `INSERT` either succeeds once or raises `IntegrityError` off the
   existing `UNIQUE(voter_id, deal_date)` constraint, caught and turned into a 400 —
   atomic by construction, no separate check-then-insert race). `static/builder.html`
   checks `/api/deals/today` for the caller's own entry on load and shows a locked
   "already submitted" view instead of the basket UI when found.
4. **Basket reset on submit** — `static/builder.html`: `basket.clear()` +
   `renderBasket()` right after a successful submit, before the toast/redirect;
   `submit_deal` also clears that day's `basket_drafts` row server-side.

> **Status:** Shipped.

## v0.3.6 — Honourable mentions, barcode realism

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Admin-created "honourable mention" combos | M | User request: funky, admin-curated 30-Wimbledon combos for laughs, visible but explicitly outside the competitive ranking |
| 2 | Denser, more realistic barcode rendering | XS | User supplied a reference photo of an actual barcode; the original render was too sparse/gappy to read as one |
| 3 | Credit-share popup gated on a minimum leftover | XS | Below the price of the cheapest catalog item (W$1.05), there's nothing to meaningfully "stock up" on |

### Item details

1. **Honourable mentions** — `main.py` (`combos.honourable` column, migrated in for
   existing DBs; `AdminComboCreate` model; `POST /api/admin/combos` — still validates
   the exact-3000-cent invariant, just flags the row instead of requiring a real
   player submission). `static/index.html` splits combos client-side into the normal
   sortable grid and a separate "🏆 Honourable Mentions" section (own grid, no sort
   toggle, excluded from `sortCombos()`); rating/commenting still work on them via
   the same delegated listeners (moved from `grid`-scoped to `document`-scoped so
   both grids share one set of handlers). `static/admin.html` gets a "+ New
   honourable mention" panel with a meal picker (see v0.3.7 — the original free-text
   entry shipped in this version was replaced almost immediately).
2. **Barcode density** — `static/wim.js` (`renderBarcode()`): gap between bars
   1px → was 3px, 5 bar segments per character (was 3), width range narrowed to
   1-4px and narrow-dominant. Still a deterministic cosmetic pattern, not a real
   Code39/Code128 encoding.
3. **Credit-share threshold** — `static/builder.html`: the popup only fires when
   `distance_cents > 105`; otherwise the normal under-30 redirect happens with no
   prompt.

> **Status:** Shipped.

## v0.3.7 — Honourable-mention picker fix, ticker banner, readable errors

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Meal picker replaces free-text item entry in the honourable-mention form | S | Live 422 on wmax.shop — an empty/mistyped emoji field violates `SnapshotItemIn`'s `min_length=1`; user reported the free-text form as clunky anyway |
| 2 | Fix `[object Object]` toast on validation errors | XS | FastAPI/pydantic 422s return `detail` as a list of `{loc, msg, type}` objects, not a string — `api()` only ever handled the string case, so any 422 anywhere in the app rendered unreadable |
| 3 | Scrolling ticker banner on Tips & Tricks | S | User-approved UX idea: top tips crawl across the screen like a news ticker, separate from the normal reactable list below |

### Item details

1. **Meal picker** — `static/admin.html`. The "+ New honourable mention" panel's
   item entry (free-text emoji/name/price/qty inputs, the same `itemRow()` used for
   editing an *existing* combo's items) is replaced by a `<select>` of the live meal
   pool (`GET /api/meals`) + a quantity field + "+ Add"; picking a meal copies its
   `emoji`/`name`/`price_cents` straight from the meal record into a `newComboItems`
   array — nothing is retyped, so the exact bug class that caused the 422 (a blank
   emoji cell) can't happen. Picked items render with `builder.html`'s
   `.basket-row`/`.qty-controls` dec/inc pattern instead of typable inputs. Editing
   an *existing* combo's items still uses the original free-text `itemEditor()` —
   unchanged, since those rows can legitimately hold a historical snapshot that no
   longer matches any current meal.
2. **Readable validation errors** — `static/wim.js` (`api()`). `detail` is now
   type-checked: a string is used as-is (the shape every hand-written
   `HTTPException(400, "...")` in the app already returns), and an array (the shape
   pydantic's automatic 422s return) has its per-field `msg`s joined instead of
   being handed straight to `new Error()`, which stringified the array into
   `"[object Object],[object Object]"`.
3. **Ticker banner** — `static/tips.html`, `static/style.css`. A `.ticker-wrap`
   above the normal tip list holds the top `TICKER_SIZE` (8) tips by score, each
   rendered once and then duplicated so a CSS `@keyframes ticker` animation
   (`translateX(0)` → `translateX(-50%)`, linear, infinite) loops seamlessly;
   paused on hover. `renderTicker()` is keyed on the joined ids of the visible
   top-N so an unrelated reaction elsewhere (which still calls `render()`) doesn't
   restart the scroll mid-loop — only a real change to the top-N set/order does.

> **Status:** Shipped.

## v0.3.8 — Merge Players into the Leaderboard

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | `/players` merges into `/`; combo cards move to a horizontal scroll strip | M | User feedback: "Leaderboard should really be the Players" — the naming was backwards, with the combo/rating page called "leaderboard" while the actual competitive ranking lived on a separate `/players` page |

### Item details

1. **One leaderboard page** — `static/index.html` gains a Players section
   (`loadToday()`/`loadOverall()`, ported from the removed `static/players.html`)
   below the combo strips, refetched on the `deal` WS event so a submission
   elsewhere updates the rankings live. `/players` route (`main.py`) and its nav
   link (`static/wim.js`) are removed; every remaining redirect/link to it
   (`static/builder.html`'s locked view, credit-share modal, and post-submit
   redirect) now points at `/`. Combo cards move from a reflowing CSS grid with a
   per-card floating/bobbing animation to a horizontally-scrolling `.combo-strip`
   (fixed-width cards, native scroll + snap) — the wandering/bobbing mechanic
   stays exclusive to the Basket Builder arena, where it originated; the shared
   `@keyframes floaty` used by the arena's `.float-chip` is untouched.

> **Status:** Shipped.

## v0.3.9 — Higher per-item quantity cap

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Raise per-item qty cap 20 → 99 | XS | User hit the 20 cap trying to add 24 of the same meal to a combo; the limit was an arbitrary guard, not a rule tied to game logic |

### Item details

1. **Qty cap** — `main.py`: `Field(ge=1, le=20)` → `le=99` on `ComboItemIn.qty`
   (combo submission + Daily Deal items), `SnapshotItemIn.qty` (admin combo
   items), and `BasketItemIn.qty` (basket draft). Matching `max="20"` → `max="99"`
   on the two qty inputs in `static/admin.html`. 99 is still a sanity bound
   (nothing in the game logic needs more), just no longer one low enough to
   block a legitimate combo/basket built from a single cheap item.

> **Status:** Shipped.

## v0.3.10 — Merge honourable mentions into the main strip

| # | Item | Effort | Why now |
|---|------|--------|---------|
| 1 | Drop the separate Honourable Mentions strip; merge into the main combo strip with a trophy-emoji marker | S | User feedback: the split section was unnecessary ceremony for a distinction that only needs a glance, not a whole separate strip |

### Item details

1. **One strip, one marker** — `static/index.html`. `sortCombos()` no longer
   filters `!c.honourable`, so honourable mentions sort, rate, and comment
   exactly like player-submitted combos — top-rated/newest now spans all of
   them together. `cardHtml()` drops the `.honourable` class and the
   `.honourable-badge` div in favor of prefixing the `<h3>` with a trophy emoji
   when `c.honourable` is set. The `#honourable-section`/`#honourable-grid`
   markup, and the now-dead `.card.honourable`/`.honourable-badge` CSS, are
   removed (`.honourable-tag`, the small inline marker used in `admin.html`'s
   combos table, is unrelated and stays).

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

**Deployment-topology risks, flagged but not fixed at the time:** `rate_limit()`
trusted `request.client.host` directly, which would collapse to one shared bucket
for everyone behind a reverse proxy unless configured to forward the real client
IP; the session cookie had no `secure` flag; `/ws/feed` had no connection cap; the
app binds `0.0.0.0` by design (LAN play), which combined with a guessable default
admin key means changing `WIM_ADMIN_KEY` before exposing this beyond a trusted LAN
is load-bearing, not optional.

> **Update (same day):** all of the above resolved in v0.3.2 once an actual
> deployment target (VPS + domain) was decided — see that section above. The
> original plan to fix proxy-trust with a custom `WIM_TRUST_PROXY` flag was itself
> replaced after testing showed it duplicated (imperfectly) what uvicorn's own
> `ProxyHeadersMiddleware` already does correctly.

**Verdict:** ready for its intended use case — a locally hosted game among a trusted
group on a LAN, or on the public internet behind the documented Caddy + systemd setup
with `WIM_ADMIN_KEY` changed from the default.

## Backlog (unscheduled)

- Configurable target (30 Wimbledons is sacred, but a "hard mode" 50-Wimbledons bracket could be fun)
- Combo duplicate detection (same multiset of items)
- Export/import database (JSON)
- Basic pytest suite: combo validation, admin auth, snapshot integrity
- CI workflow (syntax + import check, like CCD's)
- Confetti burst when the meter hits exactly 30 Wimbledons
