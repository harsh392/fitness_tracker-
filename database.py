import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "meals.db")

_shared_conn = None

NUTRITION_KEYS = ["protein", "carbs", "fat", "fiber", "sodium", "iron", "calcium", "vitamin_a", "vitamin_c", "vitamin_d", "potassium"]


def get_connection():
    global _shared_conn
    if DB_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
        return _shared_conn
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        if DB_PATH != ":memory:":
            conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_description TEXT NOT NULL,
                calories INTEGER NOT NULL,
                meal_date TEXT NOT NULL,
                meal_time TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                raw_input TEXT,
                nutrition TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meals_date_time
            ON meals(meal_date, meal_time)
        """)


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    # Parse nutrition JSON back to dict
    if d.get("nutrition"):
        try:
            d["nutrition"] = json.loads(d["nutrition"])
        except (json.JSONDecodeError, TypeError):
            d["nutrition"] = None
    return d


def insert_meal(food_description: str, calories: int, meal_date: str, meal_time: str, raw_input: str = None, nutrition: dict = None) -> dict:
    nutrition_json = json.dumps(nutrition) if nutrition else None
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO meals (food_description, calories, meal_date, meal_time, raw_input, nutrition) VALUES (?, ?, ?, ?, ?, ?)",
            (food_description, calories, meal_date, meal_time, raw_input, nutrition_json),
        )
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_dict(row)


def get_meals_by_date(meal_date: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE meal_date = ? ORDER BY meal_time ASC",
            (meal_date,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_daily_summary(meal_date: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as meal_count, COALESCE(SUM(calories), 0) as total_calories FROM meals WHERE meal_date = ?",
            (meal_date,),
        ).fetchone()
        summary = _row_to_dict(row)

        # Aggregate nutrition across all meals for the day
        rows = conn.execute(
            "SELECT nutrition FROM meals WHERE meal_date = ? AND nutrition IS NOT NULL",
            (meal_date,),
        ).fetchall()

        totals = {k: 0.0 for k in NUTRITION_KEYS}
        for r in rows:
            try:
                n = json.loads(r["nutrition"])
                for k in NUTRITION_KEYS:
                    totals[k] += float(n.get(k, 0))
            except (json.JSONDecodeError, TypeError):
                continue

        # Round for cleanliness
        summary["nutrition"] = {k: round(v, 1) for k, v in totals.items()}
        return summary


def find_conflict(meal_date: str, meal_time: str) -> dict | None:
    h, m = map(int, meal_time.split(":"))
    target_minutes = h * 60 + m

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE meal_date = ?",
            (meal_date,),
        ).fetchall()

        for row in rows:
            rh, rm = map(int, row["meal_time"].split(":"))
            row_minutes = rh * 60 + rm
            if abs(row_minutes - target_minutes) <= 30:
                return _row_to_dict(row)

    return None


def delete_meal(meal_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        return cursor.rowcount > 0


def update_meal(meal_id: int, food_description: str, calories: int, meal_date: str, meal_time: str, raw_input: str = None, nutrition: dict = None) -> dict | None:
    nutrition_json = json.dumps(nutrition) if nutrition else None
    with get_db() as conn:
        conn.execute(
            "UPDATE meals SET food_description = ?, calories = ?, meal_date = ?, meal_time = ?, raw_input = ?, nutrition = ? WHERE id = ?",
            (food_description, calories, meal_date, meal_time, raw_input, nutrition_json, meal_id),
        )
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
        return _row_to_dict(row)


def get_meal_by_id(meal_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
        return _row_to_dict(row)
