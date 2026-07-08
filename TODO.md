# TODO

Flat actionable checklist. Grouped by roadmap version — see [ROADMAP.md](ROADMAP.md)
for context on each item. Check items off as they ship.

## v0.2.0 — Fairness and live updates

- [ ] Add `voter_id` to `ratings` with UNIQUE(combo_id, voter_id); re-rating updates (#1)
- [ ] Signed session cookie + one-time display-name prompt; autofill author fields (#2)
- [ ] `/ws/feed` WebSocket broadcasting combo/rating/comment events (#3)
- [ ] Leaderboard patches cards live with a glow on change (#3)
- [ ] Admin endpoints + UI to edit combo items, preserving the 3000-cent invariant (#4)
- [ ] In-memory per-IP rate limiting on all POST endpoints (#5)

## v0.3.0 — Seasons and polish

- [ ] Season table + weekly rollover job; archive past seasons
- [ ] Hall of fame page for past season winners
- [ ] Winner podium (top 3) section on the leaderboard
- [ ] Optional meal photo upload (stored next to the DB, served statically)
- [ ] Bigger touch targets + drop feedback for mobile drag
- [ ] Dockerfile + docker-compose.yml

## Housekeeping

- [ ] pytest suite: combo total validation, admin auth, snapshot integrity, cascade deletes
- [ ] GitHub Actions CI: syntax + import check on push
- [ ] Change default admin key handling: warn on startup if WIM_ADMIN_KEY is unset

## Done (v0.1.0)

- [x] FastAPI + SQLite backend with seed data
- [x] W$ SVG glyph (W with dollar stroke) used for all prices
- [x] Leaderboard with floating cards, star ratings, comments, top/new sort
- [x] Basket Builder: drag floating meals into basket, live 30-Wimbledons meter
- [x] Add Meals page with 48-emoji picker
- [x] Admin console: meals / combos / comments tabs, key-protected
- [x] Combo snapshot model (integer cents, exact-3000 validation)
- [x] README, CLAUDE.md, ROADMAP, TODO documentation set
