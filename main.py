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
TARGET_CENTS = 3000  # exactly W$30.00
PORT = int(os.environ.get("WIM_PORT", "8030"))
COOKIE = "wim_session"


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
        """)
        # Migrate pre-0.2.0 ratings tables that lack voter_id.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(ratings)").fetchall()]
        if "voter_id" not in cols:
            conn.execute("ALTER TABLE ratings ADD COLUMN voter_id TEXT")
        # One rating per (combo, voter). NULLs are distinct in SQLite, so legacy
        # seed ratings (voter_id IS NULL) never collide.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_ratings_voter"
                     " ON ratings(combo_id, voter_id)")

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

class ConnectionManager:
    """Tracks connected leaderboard clients and fans out events to them."""

    def __init__(self):
        self.active: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

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
            max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
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
    ip = request.client.host if request.client else "?"
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
    qty: int = Field(ge=1, le=20)


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
    qty: int = Field(ge=1, le=20)


class ComboItemsUpdate(BaseModel):
    items: list[SnapshotItemIn] = Field(min_length=1)


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


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


@app.get("/deals")
def page_deals():
    return FileResponse(STATIC / "deals.html")


@app.get("/players")
def page_players():
    return FileResponse(STATIC / "players.html")


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


def deal_distance(total_cents: int) -> int:
    return abs(total_cents - TARGET_CENTS)


@app.post("/api/deals", status_code=201, dependencies=[Depends(rate_limit)])
def submit_deal(deal: DealIn, voter_id: str = Depends(get_voter)):
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
        cur = conn.execute(
            "INSERT INTO daily_deals(voter_id, deal_date, total_cents) VALUES (?,?,?)"
            " ON CONFLICT(voter_id, deal_date) DO UPDATE SET total_cents=excluded.total_cents"
            " RETURNING id",
            (voter_id, today, total))
        deal_id = cur.fetchone()["id"]
        conn.execute("DELETE FROM daily_deal_items WHERE deal_id=?", (deal_id,))
        conn.executemany(
            "INSERT INTO daily_deal_items(deal_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(deal_id, n, e, p, q) for n, e, p, q in snapshot])
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


@app.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    await MANAGER.connect(ws)
    try:
        while True:
            await ws.receive_text()  # clients don't send; this just detects disconnect
    except WebSocketDisconnect:
        MANAGER.disconnect(ws)
    except Exception:
        MANAGER.disconnect(ws)


# ---------- admin API ----------

def require_admin(key: str | None):
    if key != ADMIN_KEY:
        raise HTTPException(401, "Invalid admin key")


@app.get("/api/admin/verify")
def admin_verify(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    return {"ok": True}


@app.put("/api/admin/meals/{meal_id}")
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


@app.delete("/api/admin/meals/{meal_id}")
def admin_delete_meal(meal_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Meal not found")
    return {"ok": True}


@app.put("/api/admin/combos/{combo_id}")
def admin_update_combo(combo_id: int, upd: ComboUpdate,
                       x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("UPDATE combos SET name=?, author=? WHERE id=?",
                           (upd.name.strip(), upd.author.strip(), combo_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Combo not found")
    return {"ok": True}


@app.put("/api/admin/combos/{combo_id}/items")
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


@app.delete("/api/admin/combos/{combo_id}")
def admin_delete_combo(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM combos WHERE id=?", (combo_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Combo not found")
    notify({"type": "combo_delete", "combo_id": combo_id})
    return {"ok": True}


@app.delete("/api/admin/ratings/{combo_id}")
def admin_clear_ratings(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        conn.execute("DELETE FROM ratings WHERE combo_id=?", (combo_id,))
        stats = rating_stats(conn, combo_id)
    notify({"type": "rating", "combo_id": combo_id, **stats})
    return {"ok": True}


@app.get("/api/admin/comments")
def admin_all_comments(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        rows = conn.execute(
            "SELECT comments.*, combos.name AS combo_name FROM comments"
            " JOIN combos ON combos.id = comments.combo_id ORDER BY comments.id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/deals")
def admin_all_deals(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        rows = conn.execute(
            "SELECT d.id, d.voter_id, s.display_name AS name, d.deal_date, d.total_cents"
            " FROM daily_deals d JOIN sessions s ON s.voter_id = d.voter_id"
            " ORDER BY d.deal_date DESC, d.id DESC").fetchall()
    return [{**dict(r), "distance_cents": deal_distance(r["total_cents"])} for r in rows]


@app.delete("/api/admin/deals/{deal_id}")
def admin_delete_deal(deal_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM daily_deals WHERE id=?", (deal_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Deal not found")
    return {"ok": True}


@app.delete("/api/admin/comments/{comment_id}")
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
