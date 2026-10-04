"""SQLite storage: schema, connection helper, and starter data."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "barbershop.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS shop (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    tagline TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    parking TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    instagram TEXT NOT NULL DEFAULT '',
    cancellation_policy TEXT NOT NULL DEFAULT '',
    rules TEXT NOT NULL DEFAULT '[]',
    buffer_minutes INTEGER NOT NULL DEFAULT 10,
    slot_interval INTEGER NOT NULL DEFAULT 15,
    min_notice_minutes INTEGER NOT NULL DEFAULT 120,
    max_days_ahead INTEGER NOT NULL DEFAULT 28
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    duration_min INTEGER NOT NULL,
    price_cents INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weekly_hours (
    weekday INTEGER PRIMARY KEY CHECK (weekday BETWEEN 0 AND 6),
    is_open INTEGER NOT NULL DEFAULT 0,
    open_time TEXT NOT NULL DEFAULT '10:00',
    close_time TEXT NOT NULL DEFAULT '18:00'
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    service_id INTEGER NOT NULL REFERENCES services(id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'cancelled')),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(start_at);
CREATE INDEX IF NOT EXISTS idx_blocks_start ON blocks(start_at);
"""

STARTER_RULES = [
    "Please arrive 5 minutes early. If you're more than 10 minutes late we may need to reschedule.",
    "Need to cancel? Give at least 12 hours' notice so someone else can take the spot.",
    "Two no-shows and we'll ask for a deposit on future bookings.",
    "Card and cash both welcome. Tips appreciated, never expected.",
    "Kids under 12 should come with an adult.",
]

STARTER_SERVICES = [
    ("Classic cut", "Scissor or clipper cut, styled and finished.", 30, 3500),
    ("Skin fade", "Fade down to the skin, blended into any length on top.", 45, 4500),
    ("Cut + beard", "Any haircut plus a beard trim and line-up.", 60, 6000),
    ("Beard trim", "Shape, trim and a sharp line-up with a hot towel.", 20, 2000),
    ("Kids cut", "For ages 12 and under.", 30, 2800),
]

# weekday: 0 = Monday ... 6 = Sunday
STARTER_HOURS = [
    (0, 1, "10:00", "18:00"),
    (1, 1, "10:00", "18:00"),
    (2, 1, "10:00", "18:00"),
    (3, 1, "10:00", "19:00"),
    (4, 1, "09:00", "18:00"),
    (5, 1, "09:00", "16:00"),
    (6, 0, "10:00", "16:00"),
]


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection in autocommit mode; callers use explicit BEGIN for multi-step writes."""
    if path is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        path = DB_PATH
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    if conn.execute("SELECT 1 FROM shop WHERE id = 1").fetchone() is None:
        seed(conn)


def seed(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN")
    conn.execute(
        """INSERT INTO shop (id, name, tagline, address, city, parking, phone, email, instagram,
                             cancellation_policy, rules)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Celoblendzz",
            "Clean cuts, sharp fades, no fuss. Book your chair in under a minute.",
            "",
            "Irvine, CA",
            "",
            "",
            "",
            "",
            "Free to cancel or reschedule up to 12 hours before your appointment. "
            "Call or text the shop to make changes.",
            json.dumps(STARTER_RULES),
        ),
    )
    conn.executemany(
        "INSERT INTO services (name, description, duration_min, price_cents, sort_order) VALUES (?, ?, ?, ?, ?)",
        [(*service, index) for index, service in enumerate(STARTER_SERVICES)],
    )
    conn.executemany(
        "INSERT INTO weekly_hours (weekday, is_open, open_time, close_time) VALUES (?, ?, ?, ?)",
        STARTER_HOURS,
    )
    conn.execute("COMMIT")
