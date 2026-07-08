"""Wimbledon$ Maximizer — spend exactly 30 Wimbledons, rate the best combos."""
import os
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB_PATH = BASE / "wimbledon.db"
STATIC = BASE / "static"
ADMIN_KEY = os.environ.get("WIM_ADMIN_KEY", "wimbledon")
TARGET_CENTS = 3000  # exactly W$30.00
PORT = int(os.environ.get("WIM_PORT", "8030"))


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
        """)
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


app = FastAPI(title="Wimbledon$ Maximizer")
init_db()
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------- request models ----------

class MealIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(min_length=1, max_length=8)
    price: float = Field(gt=0, le=30)
    created_by: str = Field(default="", max_length=40)


class ComboItemIn(BaseModel):
    meal_id: int
    qty: int = Field(ge=1, le=20)


class ComboIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    author: str = Field(min_length=1, max_length=40)
    items: list[ComboItemIn] = Field(min_length=1)


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)


class CommentIn(BaseModel):
    author: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=500)


class ComboUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    author: str = Field(min_length=1, max_length=40)


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


@app.get("/admin")
def page_admin():
    return FileResponse(STATIC / "admin.html")


# ---------- public API ----------

@app.get("/api/meals")
def get_meals():
    with db() as conn:
        rows = conn.execute("SELECT * FROM meals ORDER BY price_cents").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/meals", status_code=201)
def add_meal(meal: MealIn):
    cents = round(meal.price * 100)
    if cents <= 0:
        raise HTTPException(400, "Price must be positive")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO meals(name, emoji, price_cents, created_by) VALUES (?,?,?,?)",
            (meal.name.strip(), meal.emoji.strip(), cents, meal.created_by.strip()))
        return {"id": cur.lastrowid}


@app.get("/api/combos")
def get_combos():
    with db() as conn:
        combos = conn.execute("SELECT * FROM combos ORDER BY id DESC").fetchall()
        out = []
        for c in combos:
            items = conn.execute(
                "SELECT meal_name, emoji, price_cents, qty FROM combo_items"
                " WHERE combo_id=?", (c["id"],)).fetchall()
            stats = conn.execute(
                "SELECT COUNT(*) n, COALESCE(AVG(stars),0) avg FROM ratings"
                " WHERE combo_id=?", (c["id"],)).fetchone()
            n_comments = conn.execute(
                "SELECT COUNT(*) FROM comments WHERE combo_id=?", (c["id"],)).fetchone()[0]
            out.append({
                "id": c["id"], "name": c["name"], "author": c["author"],
                "created_at": c["created_at"],
                "items": [dict(i) for i in items],
                "total_cents": sum(i["price_cents"] * i["qty"] for i in items),
                "rating_avg": round(stats["avg"], 2), "rating_count": stats["n"],
                "comment_count": n_comments,
            })
    return out


@app.post("/api/combos", status_code=201)
def add_combo(combo: ComboIn):
    with db() as conn:
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
            (combo.name.strip(), combo.author.strip()))
        cid = cur.lastrowid
        conn.executemany(
            "INSERT INTO combo_items(combo_id, meal_name, emoji, price_cents, qty)"
            " VALUES (?,?,?,?,?)",
            [(cid, n, e, p, q) for n, e, p, q in snapshot])
        return {"id": cid}


@app.post("/api/combos/{combo_id}/rate", status_code=201)
def rate_combo(combo_id: int, rating: RateIn):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM combos WHERE id=?", (combo_id,)).fetchone():
            raise HTTPException(404, "Combo not found")
        conn.execute("INSERT INTO ratings(combo_id, stars) VALUES (?,?)",
                     (combo_id, rating.stars))
        stats = conn.execute(
            "SELECT COUNT(*) n, AVG(stars) avg FROM ratings WHERE combo_id=?",
            (combo_id,)).fetchone()
    return {"rating_avg": round(stats["avg"], 2), "rating_count": stats["n"]}


@app.get("/api/combos/{combo_id}/comments")
def get_comments(combo_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, author, text, created_at FROM comments"
            " WHERE combo_id=? ORDER BY id", (combo_id,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/combos/{combo_id}/comments", status_code=201)
def add_comment(combo_id: int, comment: CommentIn):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM combos WHERE id=?", (combo_id,)).fetchone():
            raise HTTPException(404, "Combo not found")
        cur = conn.execute(
            "INSERT INTO comments(combo_id, author, text) VALUES (?,?,?)",
            (combo_id, comment.author.strip(), comment.text.strip()))
        return {"id": cur.lastrowid}


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


@app.delete("/api/admin/combos/{combo_id}")
def admin_delete_combo(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM combos WHERE id=?", (combo_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Combo not found")
    return {"ok": True}


@app.delete("/api/admin/ratings/{combo_id}")
def admin_clear_ratings(combo_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        conn.execute("DELETE FROM ratings WHERE combo_id=?", (combo_id,))
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


@app.delete("/api/admin/comments/{comment_id}")
def admin_delete_comment(comment_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    with db() as conn:
        cur = conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Comment not found")
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
