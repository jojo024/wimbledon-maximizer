"""Wimbledon$ Maximizer — spend exactly 30 Wimbledons, rate the best combos."""
import asyncio
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import uvicorn
from fastapi import (Depends, FastAPI, Header, HTTPException, Request, Response,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB_PATH = BASE / "wimbledon.db"
STATIC = BASE / "static"
SECRET_PATH = BASE / ".wim_secret"
ADMIN_KEY = os.environ.get("WIM_ADMIN_KEY", "wimbledon")
# Strawberry Rush is a separate repo (github.com/jojo024/strawberry-rush) — a
# zero-dependency static Canvas game, cloned as a sibling checkout and served
# read-only under /play. It has its own git history, its own README, and its
# own release cadence; this app never imports or builds any part of it.
GAME_DIR = Path(os.environ.get("WIM_GAME_DIR", str(BASE.parent / "strawberry-rush")))
# Broadcast Wordle (github.com/NickPoopy/broadcast-wordle) is likewise a
# separate repo, but a built Vite/React app rather than zero-dependency static
# files — WORDLE_DIR points at its *built* `dist/`, produced with
# `VITE_BASE_PATH=/wordle/ npm run build` in that other checkout, not at the
# repo root. Same read-only, no-import mounting as Strawberry Rush otherwise.
WORDLE_DIR = Path(os.environ.get("WIM_WORDLE_DIR", str(BASE.parent / "broadcast-wordle" / "dist")))
TARGET_CENTS = 3000  # exactly W$30.00
HOST = os.environ.get("WIM_HOST", "0.0.0.0")
PORT = int(os.environ.get("WIM_PORT", "8030"))
COOKIE = "wim_session"

# uvicorn's own ProxyHeadersMiddleware (always on) already trusts
# X-Forwarded-For/X-Forwarded-Proto — but *only* from connections whose
# direct peer address is in FORWARDED_ALLOW_IPS — and rewrites request.client
# / request.url.scheme accordingly before this app ever sees the request. So
# application code just reads those normally; it must never re-parse the
# raw headers itself (that reimplementation is exactly where a first-vs-last
# entry bug would let a client spoof its own IP). Default trusts only
# loopback, matching the documented WIM_HOST=127.0.0.1-behind-Caddy setup.
FORWARDED_ALLOW_IPS = os.environ.get("WIM_FORWARDED_ALLOW_IPS", "127.0.0.1")


def _load_secret() -> bytes:
    """Persistent HMAC secret for signing session cookies (survives restarts)."""
    env = os.environ.get("WIM_SECRET")
    if env:
        return env.encode()
    if SECRET_PATH.exists():
        return SECRET_PATH.read_bytes()
    value = secrets.token_bytes(32)
    SECRET_PATH.write_bytes(value)
    return value


SECRET = _load_secret()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SEED_MEALS = [
    ("Croissant", "🥐", 450), ("Espresso", "☕", 300), ("Ramen bowl", "🍜", 1200),
    ("Sushi set", "🍣", 950), ("Pizza slice", "🍕", 600), ("Green salad", "🥗", 750),
    ("Boba tea", "🧋", 500), ("Smash burger", "🍔", 1000), ("Apple", "🍎", 200),
    ("Donut", "🍩", 350), ("Strawberries", "🍓", 400), ("Taco", "🌮", 550),
    ("Avocado toast", "🥑", 850), ("Ice cream", "🍦", 450), ("Fries", "🍟", 400),
    ("Grapes", "🍇", 300), ("Cookie", "🍪", 250), ("Pancakes", "🥞", 700),
]

SEED_COMBOS = [
    ("The Founder's Feast", "Admin",
     [("Ramen bowl", "🍜", 1200, 1), ("Smash burger", "🍔", 1000, 1),
      ("Boba tea", "🧋", 500, 1), ("Espresso", "☕", 300, 1)]),
    ("Green Machine", "Admin",
     [("Pizza slice", "🍕", 600, 1), ("Green salad", "🥗", 750, 1),
      ("Avocado toast", "🥑", 850, 1), ("Boba tea", "🧋", 500, 1),
      ("Espresso", "☕", 300, 1)]),
]


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS meals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents > 0),
            created_by TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS combos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            honourable INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS combo_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_id INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
            meal_name TEXT NOT NULL,
            emoji TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            qty INTEGER NOT NULL CHECK(qty > 0)
        );
        CREATE TABLE IF NOT EXISTS ratings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_id INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
            voter_id TEXT,
            stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS comments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_id INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions(
            voter_id TEXT PRIMARY KEY,
            display_name TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS comment_votes(
            comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
            voter_id TEXT NOT NULL,
            PRIMARY KEY (comment_id, voter_id)
        );
        CREATE TABLE IF NOT EXISTS daily_deals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id TEXT NOT NULL,
            deal_date TEXT NOT NULL,
            total_cents INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(voter_id, deal_date)
        );
        CREATE TABLE IF NOT EXISTS daily_deal_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL REFERENCES daily_deals(id) ON DELETE CASCADE,
            meal_name TEXT NOT NULL,
            emoji TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            qty INTEGER NOT NULL CHECK(qty > 0)
        );
        CREATE TABLE IF NOT EXISTS tips(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tip_votes(
            tip_id INTEGER NOT NULL REFERENCES tips(id) ON DELETE CASCADE,
            voter_id TEXT NOT NULL,
            PRIMARY KEY (tip_id, voter_id)
        );
        CREATE TABLE IF NOT EXISTS tip_reactions(
            tip_id INTEGER NOT NULL REFERENCES tips(id) ON DELETE CASCADE,
            voter_id TEXT NOT NULL,
            reaction TEXT NOT NULL CHECK(reaction IN ('up','down','fire','heart','laugh','cry')),
            PRIMARY KEY (tip_id, voter_id, reaction)
        );
        CREATE TABLE IF NOT EXISTS basket_drafts(
            voter_id TEXT NOT NULL,
            basket_date TEXT NOT NULL,
            meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            qty INTEGER NOT NULL CHECK(qty > 0),
            PRIMARY KEY (voter_id, basket_date, meal_id)
        );
        """)
        # Migrate pre-0.2.0 ratings tables that lack voter_id.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(ratings)").fetchall()]
        if "voter_id" not in cols:
            conn.execute("ALTER TABLE ratings ADD COLUMN voter_id TEXT")
        # One rating per (combo, voter). NULLs are distinct in SQLite, so legacy
        # seed ratings (voter_id IS NULL) never collide.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_ratings_voter"
                     " ON ratings(combo_id, voter_id)")
        # Migrate pre-0.3.5 single-upvote tips into the richer reaction model
        # (up/down/fire/heart/laugh/cry). Idempotent — INSERT OR IGNORE means
        # re-running this after the first migration is a harmless no-op.
        conn.execute(
            "INSERT OR IGNORE INTO tip_reactions(tip_id, voter_id, reaction)"
            " SELECT tip_id, voter_id, 'up' FROM tip_votes")
        # Migrate pre-0.3.6 combos tables that lack the honourable flag.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(combos)").fetchall()]
        if "honourable" not in cols:
            conn.execute("ALTER TABLE combos ADD COLUMN honourable INTEGER NOT NULL DEFAULT 0")

        if conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO meals(name, emoji, price_cents, created_by) VALUES (?,?,?,'seed')",
                SEED_MEALS)
            for name, author, items in SEED_COMBOS:
                cur = conn.execute(
                    "INSERT INTO combos(name, author) VALUES (?,?)", (name, author))
                cid = cur.lastrowid
                conn.executemany(
                    "INSERT INTO combo_items(combo_id, meal_name, emoji, price_cents, qty)"
                    " VALUES (?,?,?,?,?)",
                    [(cid, n, e, p, q) for n, e, p, q in items])
                conn.execute("INSERT INTO ratings(combo_id, stars) VALUES (?,?)", (cid, 5))
            conn.execute(
                "INSERT INTO comments(combo_id, author, text) VALUES (1,'Admin',"
                "'The combo that started it all. Beat it if you can.')")


# ---------- live feed (WebSocket) ----------

MAX_WS_TOTAL = 500   # generous for a friend-group game; bounded so it can't be exhausted
MAX_WS_PER_IP = 8     # one browser can hold a few tabs open; more than that is abuse


class ConnectionManager:
    """Tracks connected leaderboard clients and fans out events to them."""

    def __init__(self):
        self.active: set[WebSocket] = set()
        self.by_ip: dict[str, int] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket, ip: str) -> bool:
        """Accept unless global or per-IP caps are already full. Returns whether
        the connection was accepted (caller should stop if False)."""
        if len(self.active) >= MAX_WS_TOTAL or self.by_ip.get(ip, 0) >= MAX_WS_PER_IP:
            await ws.close(code=1013)  # "try again later"
            return False
        await ws.accept()
        self.active.add(ws)
        self.by_ip[ip] = self.by_ip.get(ip, 0) + 1
        return True

    def disconnect(self, ws: WebSocket, ip: str):
        self.active.discard(ws)
        if ip in self.by_ip:
            self.by_ip[ip] -= 1
            if self.by_ip[ip] <= 0:
                del self.by_ip[ip]

    async def broadcast(self, event: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(event)
            except Exception:
                self.active.discard(ws)


MANAGER = ConnectionManager()


def notify(event: dict):
    """Fire-and-forget broadcast, safe to call from sync (threadpool) routes."""
    loop = MANAGER.loop
    if loop is not None:
        asyncio.run_coroutine_threadsafe(MANAGER.broadcast(event), loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    MANAGER.loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="Wimbledon$ Maximizer", lifespan=lifespan)
init_db()
app.mount("/static", StaticFiles(directory=STATIC), name="static")
if GAME_DIR.is_dir():
    app.mount("/play", StaticFiles(directory=GAME_DIR, html=True), name="play")
else:
    print(f"NOTE: Strawberry Rush not found at {GAME_DIR} — /play is disabled."
          f" Clone github.com/jojo024/strawberry-rush there (or set"
          f" WIM_GAME_DIR) to enable it.", flush=True)
if WORDLE_DIR.is_dir():
    app.mount("/wordle", StaticFiles(directory=WORDLE_DIR, html=True), name="wordle")
else:
    print(f"NOTE: Broadcast Wordle build not found at {WORDLE_DIR} — /wordle is"
          f" disabled. Clone github.com/NickPoopy/broadcast-wordle as a sibling"
          f" checkout and run 'VITE_BASE_PATH=/wordle/ npm run build' there (or"
          f" set WIM_WORDLE_DIR) to enable it.", flush=True)


# ---------- request origin (proxy-aware) ----------

def client_ip(request: Request | WebSocket) -> str:
    """Real client IP. uvicorn's ProxyHeadersMiddleware has already resolved
    this from X-Forwarded-For if (and only if) the direct peer is in
    FORWARDED_ALLOW_IPS — reading request.client here directly, rather than
    re-parsing the header ourselves, is what keeps that trust boundary in
    one place instead of two (mis-)implementations of it."""
    return request.client.host if request.client else "?"


def is_https(request: Request) -> bool:
    """Whether the ORIGINAL request was HTTPS — already resolved from
    X-Forwarded-Proto by uvicorn's ProxyHeadersMiddleware under the same
    trust rule as client_ip()."""
    return request.url.scheme == "https"


# ---------- session identity ----------

def sign(voter_id: str) -> str:
    return hmac.new(SECRET, voter_id.encode(), hashlib.sha256).hexdigest()[:32]


def parse_cookie(raw: str | None) -> str | None:
    if not raw or "." not in raw:
        return None
    voter_id, sig = raw.rsplit(".", 1)
    if voter_id and hmac.compare_digest(sig, sign(voter_id)):
        return voter_id
    return None


def get_voter(request: Request, response: Response) -> str:
    """Return the caller's voter id, minting + setting a signed cookie if absent."""
    voter_id = parse_cookie(request.cookies.get(COOKIE))
    if not voter_id:
        voter_id = secrets.token_urlsafe(16)
        response.set_cookie(
            COOKIE, f"{voter_id}.{sign(voter_id)}",
            max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax",
            secure=is_https(request))
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO sessions(voter_id) VALUES (?)", (voter_id,))
    return voter_id


def display_name(conn, voter_id: str) -> str:
    row = conn.execute(
        "SELECT display_name FROM sessions WHERE voter_id=?", (voter_id,)).fetchone()
    return row["display_name"] if row else ""


def require_named(conn, voter_id: str) -> str:
    """The author of anything posted is always the session's own display name —
    never a client-supplied string — so nobody can post as somebody else."""
    name = display_name(conn, voter_id)
    if not name:
        raise HTTPException(400, "Set a display name before posting (see the name prompt).")
    return name


# ---------- rate limiting ----------

RATE_BUCKETS: dict[str, tuple[float, float]] = {}
RATE_CAP = 30.0        # burst size
RATE_REFILL = 0.5      # tokens per second (~1 write every 2s sustained)


def rate_limit(request: Request):
    ip = client_ip(request)
    now = time.monotonic()
    tokens, last = RATE_BUCKETS.get(ip, (RATE_CAP, now))
    tokens = min(RATE_CAP, tokens + (now - last) * RATE_REFILL)
    if tokens < 1:
        RATE_BUCKETS[ip] = (tokens, now)
        raise HTTPException(
            429, "Whoa — you're spending Wimbledons faster than we can count them."
                 " Give it a moment.")
    RATE_BUCKETS[ip] = (tokens - 1, now)


# ---------- request models ----------

class MealIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(min_length=1, max_length=8)
    price: float = Field(gt=0, le=30)


class ComboItemIn(BaseModel):
    meal_id: int
    qty: int = Field(ge=1, le=99)


class ComboIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    items: list[ComboItemIn] = Field(min_length=1)


class DealIn(BaseModel):
    items: list[ComboItemIn] = Field(min_length=1)


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ComboUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    author: str = Field(min_length=1, max_length=40)


class SnapshotItemIn(BaseModel):
    meal_name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(min_length=1, max_length=8)
    price_cents: int = Field(gt=0, le=3000)
    qty: int = Field(ge=1, le=99)


class ComboItemsUpdate(BaseModel):
    items: list[SnapshotItemIn] = Field(min_length=1)


class AdminComboCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    author: str = Field(min_length=1, max_length=40)
    items: list[SnapshotItemIn] = Field(min_length=1)


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class TipIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


REACTIONS = ("up", "down", "fire", "heart", "laugh", "cry")


class ReactIn(BaseModel):
    reaction: str = Field(min_length=1, max_length=10)


class AdminTextUpdate(BaseModel):
    author: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=500)


class BasketItemIn(BaseModel):
    meal_id: int
    qty: int = Field(ge=1, le=99)


class BasketIn(BaseModel):
    items: list[BasketItemIn] = Field(default_factory=list)  # empty list clears the draft


# ---------- serialization ----------

def serialize_combo(conn, c, voter_id: str | None = None) -> dict:
    items = conn.execute(
        "SELECT id, meal_name, emoji, price_cents, qty FROM combo_items"
        " WHERE combo_id=?", (c["id"],)).fetchall()
    stats = conn.execute(
        "SELECT COUNT(*) n, COALESCE(AVG(stars),0) avg FROM ratings"
        " WHERE combo_id=?", (c["id"],)).fetchone()
    n_comments = conn.execute(
        "SELECT COUNT(*) FROM comments WHERE combo_id=?", (c["id"],)).fetchone()[0]
    my_rating = None
    if voter_id:
        row = conn.execute(
            "SELECT stars FROM ratings WHERE combo_id=? AND voter_id=?",
            (c["id"], voter_id)).fetchone()
        my_rating = row["stars"] if row else None
    return {
        "id": c["id"], "name": c["name"], "author": c["author"],
        "honourable": bool(c["honourable"]),
        "created_at": c["created_at"],
        "items": [dict(i) for i in items],
        "total_cents": sum(i["price_cents"] * i["qty"] for i in items),
        "rating_avg": round(stats["avg"], 2), "rating_count": stats["n"],
        "comment_count": n_comments, "my_rating": my_rating,
        "top_comment": top_comment(conn, c["id"]),
    }


def rating_stats(conn, combo_id: int) -> dict:
    stats = conn.execute(
        "SELECT COUNT(*) n, COALESCE(AVG(stars),0) avg FROM ratings WHERE combo_id=?",
        (combo_id,)).fetchone()
    return {"rating_avg": round(stats["avg"], 2), "rating_count": stats["n"]}


def top_comment(conn, combo_id: int) -> dict | None:
    """Highest-upvoted comment for a combo, or None if no comment has any votes."""
    row = conn.execute(
        "SELECT c.author, c.text, COUNT(v.voter_id) AS votes FROM comments c"
        " LEFT JOIN comment_votes v ON v.comment_id = c.id"
        " WHERE c.combo_id=? GROUP BY c.id ORDER BY votes DESC, c.id ASC LIMIT 1",
        (combo_id,)).fetchone()
    if not row or row["votes"] == 0:
        return None
    return {"author": row["author"], "text": row["text"], "votes": row["votes"]}


# ---------- pages ----------

@app.get("/")
def page_index():
    return FileResponse(STATIC / "index.html")


@app.get("/builder")
def page_builder():
    return FileResponse(STATIC / "builder.html")


@app.get("/meals")
def page_meals():
    return FileResponse(STATIC / "meals.html")


@app.get("/tips")
def page_tips():
    return FileResponse(STATIC / "tips.html")


@app.get("/admin")
def page_admin():
    return FileResponse(STATIC / "admin.html")


# ---------- session API ----------

@app.get("/api/session")
def get_session(voter_id: str = Depends(get_voter)):
    with db() as conn:
        return {"voter_id": voter_id, "name": display_name(conn, voter_id)}


@app.post("/api/session/name", dependencies=[Depends(rate_limit)])
def set_session_name(payload: NameIn, voter_id: str = Depends(get_voter)):
    name = payload.name.strip()
    with db() as conn:
        if display_name(conn, voter_id):
            raise HTTPException(400, "Your name is already set and can't be changed.")
        conn.execute(
            "INSERT INTO sessions(voter_id, display_name) VALUES (?,?)"
            " ON CONFLICT(voter_id) DO UPDATE SET display_name=excluded.display_name",
            (voter_id, name))
    return {"name": name}


# ---------- public API ----------

@app.get("/api/meals")
def get_meals():
    with db() as conn:
        rows = conn.execute("SELECT * FROM meals ORDER BY price_cents").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/meals", status_code=201, dependencies=[Depends(rate_limit)])
def add_meal(meal: MealIn, voter_id: str = Depends(get_voter)):
    cents = round(meal.price * 100)
    if cents <= 0:
        raise HTTPException(400, "Price must be positive")
    with db() as conn:
        created_by = require_named(conn, voter_id)
        cur = conn.execute(
            "INSERT INTO meals(name, emoji, price_cents, created_by) VALUES (?,?,?,?)",
            (meal.name.strip(), meal.emoji.strip(), cents, created_by))
        return {"id": cur.lastrowid}


@app.get("/api/combos")
def get_combos(voter_id: str = Depends(get_voter)):
    with db() as conn:
        combos = conn.execute("SELECT * FROM combos ORDER BY id DESC").fetchall()
        return [serialize_combo(conn, c, voter_id) for c in combos]


@app.post("/api/combos", status_code=201, dependencies=[Depends(rate_limit)])
def add_combo(combo: ComboIn, voter_id: str = Depends(get_voter)):
    with db() as conn:
        author = require_named(conn, voter_id)
        snapshot = []
        total = 0
        for item in combo.items:
            meal = conn.execute("SELECT * FROM meals WHERE id=?", (item.meal_id,)).fetchone()
            if not meal:
                raise HTTPException(404, f"Meal {item.meal_id} not found")
            snapshot.append((meal["name"], meal["emoji"], meal["price_cents"], item.qty))
            total += meal["price_cents"] * item.qty
        if total != TARGET_CENTS:
            raise HTTPException(
                400, f"Combo must total exactly 30 Wimbledons — got W${total / 100:.2f}")
        cur = conn.execute(
            "INSERT INTO combos(name, author) VALUES (?,?)",
            (combo.name.strip(), author))
        cid = cur.lastrowid
        conn.executemany(
            "INSERT INTO combo_items(combo_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(cid, n, e, p, q) for n, e, p, q in snapshot])
        combo_row = conn.execute("SELECT * FROM combos WHERE id=?", (cid,)).fetchone()
        payload = serialize_combo(conn, combo_row)
    notify({"type": "combo_new", "combo": payload})
    return {"id": cid}


@app.post("/api/combos/{combo_id}/rate", status_code=201,
          dependencies=[Depends(rate_limit)])
def rate_combo(combo_id: int, rating: RateIn, voter_id: str = Depends(get_voter)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM combos WHERE id=?", (combo_id,)).fetchone():
            raise HTTPException(404, "Combo not found")
        conn.execute(
            "INSERT INTO ratings(combo_id, voter_id, stars) VALUES (?,?,?)"
            " ON CONFLICT(combo_id, voter_id) DO UPDATE SET stars=excluded.stars",
            (combo_id, voter_id, rating.stars))
        stats = rating_stats(conn, combo_id)
    notify({"type": "rating", "combo_id": combo_id, **stats})
    return {**stats, "my_rating": rating.stars}


@app.get("/api/combos/{combo_id}/comments")
def get_comments(combo_id: int, voter_id: str = Depends(get_voter)):
    with db() as conn:
        rows = conn.execute(
            "SELECT c.id, c.author, c.text, c.created_at,"
            " COUNT(v.voter_id) AS votes,"
            " MAX(CASE WHEN v.voter_id=? THEN 1 ELSE 0 END) AS my_vote"
            " FROM comments c LEFT JOIN comment_votes v ON v.comment_id = c.id"
            " WHERE c.combo_id=? GROUP BY c.id ORDER BY votes DESC, c.id ASC",
            (voter_id, combo_id)).fetchall()
    return [{**dict(r), "my_vote": bool(r["my_vote"])} for r in rows]


@app.post("/api/combos/{combo_id}/comments", status_code=201,
          dependencies=[Depends(rate_limit)])
def add_comment(combo_id: int, comment: CommentIn, voter_id: str = Depends(get_voter)):
    with db() as conn:
        author = require_named(conn, voter_id)
        if not conn.execute("SELECT 1 FROM combos WHERE id=?", (combo_id,)).fetchone():
            raise HTTPException(404, "Combo not found")
        cur = conn.execute(
            "INSERT INTO comments(combo_id, author, text) VALUES (?,?,?)",
            (combo_id, author, comment.text.strip()))
        n = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE combo_id=?", (combo_id,)).fetchone()[0]
        tc = top_comment(conn, combo_id)
    notify({"type": "comment", "combo_id": combo_id, "comment_count": n, "top_comment": tc})
    return {"id": cur.lastrowid}


@app.post("/api/comments/{comment_id}/vote", dependencies=[Depends(rate_limit)])
def vote_comment(comment_id: int, voter_id: str = Depends(get_voter)):
    with db() as conn:
        row = conn.execute(
            "SELECT combo_id FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Comment not found")
        combo_id = row["combo_id"]
        existing = conn.execute(
            "SELECT 1 FROM comment_votes WHERE comment_id=? AND voter_id=?",
            (comment_id, voter_id)).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM comment_votes WHERE comment_id=? AND voter_id=?",
                (comment_id, voter_id))
            my_vote = False
        else:
            conn.execute(
                "INSERT INTO comment_votes(comment_id, voter_id) VALUES (?,?)",
                (comment_id, voter_id))
            my_vote = True
        votes = conn.execute(
            "SELECT COUNT(*) FROM comment_votes WHERE comment_id=?",
            (comment_id,)).fetchone()[0]
        tc = top_comment(conn, combo_id)
    notify({"type": "comment_vote", "combo_id": combo_id, "comment_id": comment_id,
            "votes": votes, "top_comment": tc})
    return {"votes": votes, "my_vote": my_vote}


def tip_reaction_counts(conn, tip_id: int) -> dict:
    rows = conn.execute(
        "SELECT reaction, COUNT(*) n FROM tip_reactions WHERE tip_id=? GROUP BY reaction",
        (tip_id,)).fetchall()
    counts = {r: 0 for r in REACTIONS}
    for row in rows:
        counts[row["reaction"]] = row["n"]
    return counts


@app.get("/api/tips")
def get_tips(voter_id: str = Depends(get_voter)):
    with db() as conn:
        rows = conn.execute(
            "SELECT t.id, t.author, t.text, t.created_at,"
            " SUM(CASE WHEN r.reaction='up' THEN 1 ELSE 0 END) AS up,"
            " SUM(CASE WHEN r.reaction='down' THEN 1 ELSE 0 END) AS down,"
            " SUM(CASE WHEN r.reaction='fire' THEN 1 ELSE 0 END) AS fire,"
            " SUM(CASE WHEN r.reaction='heart' THEN 1 ELSE 0 END) AS heart,"
            " SUM(CASE WHEN r.reaction='laugh' THEN 1 ELSE 0 END) AS laugh,"
            " SUM(CASE WHEN r.reaction='cry' THEN 1 ELSE 0 END) AS cry,"
            " GROUP_CONCAT(CASE WHEN r.voter_id=? THEN r.reaction END) AS mine_csv"
            " FROM tips t LEFT JOIN tip_reactions r ON r.tip_id = t.id"
            " GROUP BY t.id",
            (voter_id,)).fetchall()
    out = [{
        "id": r["id"], "author": r["author"], "text": r["text"], "created_at": r["created_at"],
        "counts": {k: r[k] for k in REACTIONS},
        "score": r["up"] - r["down"],
        "my_reactions": [x for x in (r["mine_csv"] or "").split(",") if x],
    } for r in rows]
    out.sort(key=lambda t: (-t["score"], -t["id"]))
    return out


@app.post("/api/tips", status_code=201, dependencies=[Depends(rate_limit)])
def add_tip(tip: TipIn, voter_id: str = Depends(get_voter)):
    with db() as conn:
        author = require_named(conn, voter_id)
        cur = conn.execute(
            "INSERT INTO tips(author, text) VALUES (?,?)", (author, tip.text.strip()))
        tip_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, author, text, created_at FROM tips WHERE id=?", (tip_id,)).fetchone()
    payload = {
        **dict(row), "counts": {r: 0 for r in REACTIONS}, "score": 0, "my_reactions": [],
    }
    notify({"type": "tip_new", "tip": payload})
    return {"id": tip_id}


@app.post("/api/tips/{tip_id}/react", dependencies=[Depends(rate_limit)])
def react_tip(tip_id: int, payload: ReactIn, voter_id: str = Depends(get_voter)):
    if payload.reaction not in REACTIONS:
        raise HTTPException(400, "Unknown reaction")
    with db() as conn:
        if not conn.execute("SELECT 1 FROM tips WHERE id=?", (tip_id,)).fetchone():
            raise HTTPException(404, "Tip not found")
        existing = conn.execute(
            "SELECT 1 FROM tip_reactions WHERE tip_id=? AND voter_id=? AND reaction=?",
            (tip_id, voter_id, payload.reaction)).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM tip_reactions WHERE tip_id=? AND voter_id=? AND reaction=?",
                (tip_id, voter_id, payload.reaction))
            mine = False
        else:
            conn.execute(
                "INSERT INTO tip_reactions(tip_id, voter_id, reaction) VALUES (?,?,?)",
                (tip_id, voter_id, payload.reaction))
            mine = True
        counts = tip_reaction_counts(conn, tip_id)
    notify({"type": "tip_react", "tip_id": tip_id, "counts": counts,
            "score": counts["up"] - counts["down"]})
    return {"counts": counts, "reaction": payload.reaction, "mine": mine}


def deal_distance(total_cents: int) -> int:
    return abs(total_cents - TARGET_CENTS)


@app.post("/api/deals", status_code=201, dependencies=[Depends(rate_limit)])
def submit_deal(deal: DealIn, voter_id: str = Depends(get_voter)):
    """One submission per (voter, day) — no correcting a resubmit. The
    UNIQUE(voter_id, deal_date) constraint is what actually enforces this;
    the INSERT either succeeds once or raises IntegrityError, so there's no
    check-then-insert race between two tabs submitting at once."""
    with db() as conn:
        name = require_named(conn, voter_id)
        snapshot = []
        total = 0
        for item in deal.items:
            meal = conn.execute("SELECT * FROM meals WHERE id=?", (item.meal_id,)).fetchone()
            if not meal:
                raise HTTPException(404, f"Meal {item.meal_id} not found")
            snapshot.append((meal["name"], meal["emoji"], meal["price_cents"], item.qty))
            total += meal["price_cents"] * item.qty
        today = date.today().isoformat()
        try:
            cur = conn.execute(
                "INSERT INTO daily_deals(voter_id, deal_date, total_cents) VALUES (?,?,?)",
                (voter_id, today, total))
        except sqlite3.IntegrityError:
            raise HTTPException(
                400, "You've already submitted today's Daily Deal — come back tomorrow.")
        deal_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO daily_deal_items(deal_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(deal_id, n, e, p, q) for n, e, p, q in snapshot])
        conn.execute(
            "DELETE FROM basket_drafts WHERE voter_id=? AND basket_date=?", (voter_id, today))
    notify({"type": "deal", "voter_id": voter_id, "name": name,
            "deal_date": today, "total_cents": total, "distance_cents": deal_distance(total)})
    return {"id": deal_id, "deal_date": today, "total_cents": total,
            "distance_cents": deal_distance(total)}


@app.get("/api/deals/today")
def deals_today(voter_id: str = Depends(get_voter)):
    today = date.today().isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT d.voter_id, s.display_name AS name, d.total_cents, d.id"
            " FROM daily_deals d JOIN sessions s ON s.voter_id = d.voter_id"
            " WHERE d.deal_date=? AND s.display_name != ''", (today,)).fetchall()
    out = [{
        "voter_id": r["voter_id"], "name": r["name"], "total_cents": r["total_cents"],
        "distance_cents": deal_distance(r["total_cents"]), "mine": r["voter_id"] == voter_id,
    } for r in rows]
    out.sort(key=lambda r: r["distance_cents"])
    return {"deal_date": today, "entries": out}


@app.get("/api/deals/leaderboard")
def deals_leaderboard():
    """All-time standings: average distance-from-30 per day since each player's first
    submission, counting any day they skipped since then as W$0 spent (max distance).
    Streak = consecutive days up to today (or yesterday, if today isn't logged yet)."""
    today = date.today()
    with db() as conn:
        deal_rows = conn.execute(
            "SELECT d.voter_id, s.display_name AS name, d.deal_date, d.total_cents"
            " FROM daily_deals d JOIN sessions s ON s.voter_id = d.voter_id"
            " WHERE s.display_name != ''").fetchall()

    by_voter: dict[str, dict] = {}
    for r in deal_rows:
        entry = by_voter.setdefault(r["voter_id"], {"name": r["name"], "days": {}})
        entry["days"][r["deal_date"]] = r["total_cents"]

    results = []
    for voter_id, entry in by_voter.items():
        days = entry["days"]
        join_date = date.fromisoformat(min(days))
        span = (today - join_date).days + 1
        total_distance = sum(
            deal_distance(days.get((join_date + timedelta(days=i)).isoformat(), 0))
            for i in range(span))
        streak = 0
        cursor = today if today.isoformat() in days else today - timedelta(days=1)
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        results.append({
            "voter_id": voter_id, "name": entry["name"],
            "days_tracked": span, "days_submitted": len(days),
            "avg_distance_cents": round(total_distance / span),
            "streak": streak,
        })
    results.sort(key=lambda r: r["avg_distance_cents"])
    return results


@app.get("/api/basket")
def get_basket(voter_id: str = Depends(get_voter)):
    """Today's in-progress basket for the caller — autosaved from the Basket
    Builder so it can be picked up on any device/visit and submitted later."""
    today = date.today().isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT b.meal_id, b.qty FROM basket_drafts b JOIN meals m ON m.id = b.meal_id"
            " WHERE b.voter_id=? AND b.basket_date=?", (voter_id, today)).fetchall()
    return {"date": today, "items": [dict(r) for r in rows]}


@app.put("/api/basket", dependencies=[Depends(rate_limit)])
def save_basket(payload: BasketIn, voter_id: str = Depends(get_voter)):
    today = date.today().isoformat()
    with db() as conn:
        conn.execute(
            "DELETE FROM basket_drafts WHERE voter_id=? AND basket_date=?", (voter_id, today))
        if payload.items:
            conn.executemany(
                "INSERT INTO basket_drafts(voter_id, basket_date, meal_id, qty) VALUES (?,?,?,?)",
                [(voter_id, today, i.meal_id, i.qty) for i in payload.items])
    return {"ok": True}


@app.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    ip = client_ip(ws)
    if not await MANAGER.connect(ws, ip):
        return
    try:
        while True:
            await ws.receive_text()  # clients don't send; this just detects disconnect
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        MANAGER.disconnect(ws, ip)


# ---------- admin API ----------

def require_admin(key: str | None):
    # Constant-time compare: a plain `!=` leaks a timing signal proportional
    # to the matching prefix length, which a network attacker could otherwise
    # use to guess the key one character at a time.
    if not key or not hmac.compare_digest(key, ADMIN_KEY):
        raise HTTPException(401, "Invalid admin key")


@app.get("/api/admin/verify", dependencies=[Depends(rate_limit)])
def admin_verify(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    return {"ok": True}


@app.put("/api/admin/meals/{meal_id}", dependencies=[Depends(rate_limit)])
def admin_update_meal(meal_id: int, meal: MealIn,
                      x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute(
            "UPDATE meals SET name=?, emoji=?, price_cents=? WHERE id=?",
            (meal.name.strip(), meal.emoji.strip(), round(meal.price * 100), meal_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Meal not found")
    return {"ok": True}


@app.delete("/api/admin/meals/{meal_id}", dependencies=[Depends(rate_limit)])
def admin_delete_meal(meal_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Meal not found")
    return {"ok": True}


@app.put("/api/admin/combos/{combo_id}", dependencies=[Depends(rate_limit)])
def admin_update_combo(combo_id: int, upd: ComboUpdate,
                       x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("UPDATE combos SET name=?, author=? WHERE id=?",
                           (upd.name.strip(), upd.author.strip(), combo_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Combo not found")
    return {"ok": True}


@app.post("/api/admin/combos", status_code=201, dependencies=[Depends(rate_limit)])
def admin_create_combo(payload: AdminComboCreate, x_admin_key: str | None = Header(default=None)):
    """Admin-authored "honourable mention" combos: still must total exactly
    3000 cents (the joke only lands if it's a real 30-Wimbledon combination),
    but flagged so the public leaderboard shows them separately and never
    factors them into the real ranking — funky, not competitive."""
    require_admin(x_admin_key)
    total = sum(i.price_cents * i.qty for i in payload.items)
    if total != TARGET_CENTS:
        raise HTTPException(
            400, f"Combo must total exactly 30 Wimbledons — got W${total / 100:.2f}")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO combos(name, author, honourable) VALUES (?,?,1)",
            (payload.name.strip(), payload.author.strip()))
        cid = cur.lastrowid
        conn.executemany(
            "INSERT INTO combo_items(combo_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(cid, i.meal_name.strip(), i.emoji.strip(), i.price_cents, i.qty)
             for i in payload.items])
        combo_row = conn.execute("SELECT * FROM combos WHERE id=?", (cid,)).fetchone()
        out = serialize_combo(conn, combo_row)
    notify({"type": "combo_new", "combo": out})
    return {"id": cid}


@app.put("/api/admin/combos/{combo_id}/items", dependencies=[Depends(rate_limit)])
def admin_update_combo_items(combo_id: int, upd: ComboItemsUpdate,
                             x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    total = sum(i.price_cents * i.qty for i in upd.items)
    if total != TARGET_CENTS:
        raise HTTPException(
            400, f"Combo must total exactly 30 Wimbledons — got W${total / 100:.2f}")
    with db() as conn:
        if not conn.execute("SELECT 1 FROM combos WHERE id=?", (combo_id,)).fetchone():
            raise HTTPException(404, "Combo not found")
        conn.execute("DELETE FROM combo_items WHERE combo_id=?", (combo_id,))
        conn.executemany(
            "INSERT INTO combo_items(combo_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(combo_id, i.meal_name.strip(), i.emoji.strip(), i.price_cents, i.qty)
             for i in upd.items])
        combo_row = conn.execute("SELECT * FROM combos WHERE id=?", (combo_id,)).fetchone()
        payload = serialize_combo(conn, combo_row)
    notify({"type": "combo_update", "combo": payload})
    return {"ok": True}


@app.delete("/api/admin/combos/{combo_id}", dependencies=[Depends(rate_limit)])
def admin_delete_combo(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM combos WHERE id=?", (combo_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Combo not found")
    notify({"type": "combo_delete", "combo_id": combo_id})
    return {"ok": True}


@app.delete("/api/admin/ratings/{combo_id}", dependencies=[Depends(rate_limit)])
def admin_clear_ratings(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        conn.execute("DELETE FROM ratings WHERE combo_id=?", (combo_id,))
        stats = rating_stats(conn, combo_id)
    notify({"type": "rating", "combo_id": combo_id, **stats})
    return {"ok": True}


@app.get("/api/admin/comments", dependencies=[Depends(rate_limit)])
def admin_all_comments(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        rows = conn.execute(
            "SELECT comments.*, combos.name AS combo_name FROM comments"
            " JOIN combos ON combos.id = comments.combo_id ORDER BY comments.id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/deals", dependencies=[Depends(rate_limit)])
def admin_all_deals(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        rows = conn.execute(
            "SELECT d.id, d.voter_id, s.display_name AS name, d.deal_date, d.total_cents"
            " FROM daily_deals d JOIN sessions s ON s.voter_id = d.voter_id"
            " ORDER BY d.deal_date DESC, d.id DESC").fetchall()
    return [{**dict(r), "distance_cents": deal_distance(r["total_cents"])} for r in rows]


@app.delete("/api/admin/deals/{deal_id}", dependencies=[Depends(rate_limit)])
def admin_delete_deal(deal_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM daily_deals WHERE id=?", (deal_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Deal not found")
    return {"ok": True}


@app.put("/api/admin/comments/{comment_id}", dependencies=[Depends(rate_limit)])
def admin_update_comment(comment_id: int, upd: AdminTextUpdate,
                         x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        row = conn.execute(
            "SELECT combo_id FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Comment not found")
        conn.execute("UPDATE comments SET author=?, text=? WHERE id=?",
                     (upd.author.strip(), upd.text.strip(), comment_id))
        combo_id = row["combo_id"]
        n = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE combo_id=?", (combo_id,)).fetchone()[0]
        tc = top_comment(conn, combo_id)
    notify({"type": "comment", "combo_id": combo_id, "comment_count": n, "top_comment": tc})
    return {"ok": True}


@app.delete("/api/admin/comments/{comment_id}", dependencies=[Depends(rate_limit)])
def admin_delete_comment(comment_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        row = conn.execute(
            "SELECT combo_id FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Comment not found")
        conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
        combo_id = row["combo_id"]
        n = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE combo_id=?", (combo_id,)).fetchone()[0]
        tc = top_comment(conn, combo_id)
    notify({"type": "comment", "combo_id": combo_id, "comment_count": n, "top_comment": tc})
    return {"ok": True}


@app.get("/api/admin/tips", dependencies=[Depends(rate_limit)])
def admin_all_tips(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        rows = conn.execute(
            "SELECT t.id, t.author, t.text, t.created_at,"
            " SUM(CASE WHEN r.reaction='up' THEN 1 ELSE 0 END) AS up,"
            " SUM(CASE WHEN r.reaction='down' THEN 1 ELSE 0 END) AS down,"
            " COUNT(r.voter_id) AS total_reactions"
            " FROM tips t LEFT JOIN tip_reactions r ON r.tip_id = t.id"
            " GROUP BY t.id ORDER BY t.id DESC").fetchall()
    return [{**dict(r), "score": r["up"] - r["down"]} for r in rows]


@app.put("/api/admin/tips/{tip_id}", dependencies=[Depends(rate_limit)])
def admin_update_tip(tip_id: int, upd: AdminTextUpdate,
                     x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute(
            "UPDATE tips SET author=?, text=? WHERE id=?",
            (upd.author.strip(), upd.text.strip(), tip_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Tip not found")
    notify({"type": "tip_update", "tip_id": tip_id,
            "author": upd.author.strip(), "text": upd.text.strip()})
    return {"ok": True}


@app.delete("/api/admin/tips/{tip_id}", dependencies=[Depends(rate_limit)])
def admin_delete_tip(tip_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM tips WHERE id=?", (tip_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Tip not found")
    notify({"type": "tip_delete", "tip_id": tip_id})
    return {"ok": True}


if __name__ == "__main__":
    if ADMIN_KEY == "wimbledon" and not os.environ.get("WIM_ADMIN_KEY"):
        print("WARNING: WIM_ADMIN_KEY is not set — using the default admin key,"
              " which is public (it's in the README). Anyone who finds this site"
              " can edit or delete the entire database. Set WIM_ADMIN_KEY before"
              " exposing this beyond a trusted LAN.", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, forwarded_allow_ips=FORWARDED_ALLOW_IPS)
