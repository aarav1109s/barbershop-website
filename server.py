#!/usr/bin/env python3
"""Barbershop website: serves the pages in public/ plus a small JSON API.

Run `python3 server.py`, then open http://localhost:8000.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import time
import traceback
from datetime import date, datetime, timedelta
from datetime import time as dtime
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from barbershop import db
from barbershop.slots import available_times, day_status, fmt_dt

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
PAGES = {"/": "index.html", "/book": "book.html", "/admin": "admin.html"}

DEFAULT_ADMIN_PASSWORD = "barber"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
SESSION_COOKIE = "admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_BODY_BYTES = 64 * 1024

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

mimetypes.add_type("text/javascript", ".js")

_sessions: dict = {}
ROUTES: list = []


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Request:
    def __init__(self, conn, params, query, body, cookies):
        self.conn = conn
        self.params = params
        self.query = query
        self.body = body
        self.cookies = cookies
        self.set_cookies: list[str] = []

    def arg(self, name):
        values = self.query.get(name)
        return values[0] if values else None


def route(method: str, pattern: str, admin: bool = False):
    def register(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn, admin))
        return fn

    return register


# ---------------------------------------------------------------- validation


def text(value, field: str, max_len: int, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"{field} must be text.")
    value = value.strip()
    if required and not value:
        raise ApiError(400, f"{field} is required.")
    if len(value) > max_len:
        raise ApiError(400, f"{field} must be {max_len} characters or fewer.")
    return value


def integer(value, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ApiError(400, f"{field} must be a whole number.")
    value = int(value)
    if not low <= value <= high:
        raise ApiError(400, f"{field} must be between {low} and {high}.")
    return value


def parse_date(value, field: str = "Date") -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"{field} must be a date like 2026-10-05.") from None


def parse_hhmm(value, field: str = "Time") -> dtime:
    if not isinstance(value, str) or not HHMM.match(value):
        raise ApiError(400, f"{field} must be a time like 14:30.")
    hour, minute = value.split(":")
    return dtime(int(hour), int(minute))


# ------------------------------------------------------------------- loaders


def load_shop(conn) -> dict:
    shop = dict(conn.execute("SELECT * FROM shop WHERE id = 1").fetchone())
    shop.pop("id")
    shop["rules"] = json.loads(shop["rules"])
    shop["hours"] = [
        {
            "weekday": row["weekday"],
            "is_open": bool(row["is_open"]),
            "open_time": row["open_time"],
            "close_time": row["close_time"],
        }
        for row in conn.execute("SELECT * FROM weekly_hours ORDER BY weekday")
    ]
    return shop


def service_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "duration_min": row["duration_min"],
        "price_cents": row["price_cents"],
        "active": bool(row["active"]),
        "sort_order": row["sort_order"],
    }


def load_service(conn, service_id, active_only: bool = True) -> dict:
    if isinstance(service_id, str) and service_id.isdigit():
        service_id = int(service_id)
    if not isinstance(service_id, int) or isinstance(service_id, bool):
        raise ApiError(400, "Pick a service first.")
    row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if row is None or (active_only and not row["active"]):
        raise ApiError(404, "That service isn't available.")
    return service_dict(row)


def booking_window_days(conn) -> int:
    return conn.execute("SELECT max_days_ahead FROM shop WHERE id = 1").fetchone()[0]


def appointment_dict(row) -> dict:
    start, end = row["start_at"], row["end_at"]
    duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds // 60
    return {
        "id": row["id"],
        "code": row["code"],
        "service": row["service_name"],
        "start": start,
        "end": end,
        "duration_min": duration,
        "price_cents": row["price_cents"],
        "name": row["customer_name"],
        "phone": row["phone"],
        "email": row["email"],
        "notes": row["notes"],
        "status": row["status"],
    }


def block_dict(row) -> dict:
    return {"id": row["id"], "start": row["start_at"], "end": row["end_at"], "reason": row["reason"]}


# --------------------------------------------------------------- public API


@route("GET", "/api/shop")
def get_shop(req):
    return load_shop(req.conn)


@route("GET", "/api/services")
def list_services(req):
    rows = req.conn.execute("SELECT * FROM services WHERE active = 1 ORDER BY sort_order, id")
    return [service_dict(row) for row in rows]


@route("GET", "/api/days")
def list_days(req):
    service = load_service(req.conn, req.arg("service_id"))
    now = datetime.now()
    return [
        {"date": day.isoformat(), "status": day_status(req.conn, day, service["duration_min"], now)}
        for day in (now.date() + timedelta(days=offset) for offset in range(booking_window_days(req.conn) + 1))
    ]


@route("GET", "/api/slots")
def list_slots(req):
    service = load_service(req.conn, req.arg("service_id"))
    day = parse_date(req.arg("date"))
    times = available_times(req.conn, day, service["duration_min"], datetime.now())
    return {"date": day.isoformat(), "times": [t.strftime("%H:%M") for t in times]}


@route("GET", "/api/next-available")
def next_available(req):
    shortest = req.conn.execute("SELECT MIN(duration_min) FROM services WHERE active = 1").fetchone()[0]
    if shortest is None:
        return {"start": None}
    now = datetime.now()
    for offset in range(booking_window_days(req.conn) + 1):
        times = available_times(req.conn, now.date() + timedelta(days=offset), shortest, now)
        if times:
            return {"start": fmt_dt(times[0])}
    return {"start": None}


def unique_code(conn) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if conn.execute("SELECT 1 FROM appointments WHERE code = ?", (code,)).fetchone() is None:
            return code


@route("POST", "/api/bookings")
def create_booking(req):
    data, conn = req.body, req.conn
    service = load_service(conn, data.get("service_id"))
    day = parse_date(data.get("date"))
    start = datetime.combine(day, parse_hhmm(data.get("time")))
    end = start + timedelta(minutes=service["duration_min"])
    name = text(data.get("name"), "Name", 80, required=True)
    phone = text(data.get("phone"), "Phone", 30, required=True)
    if len(re.sub(r"\D", "", phone)) < 7:
        raise ApiError(400, "Enter a phone number we can reach you at.")
    email = text(data.get("email"), "Email", 120)
    if email and not EMAIL.match(email):
        raise ApiError(400, "That email address doesn't look right.")
    notes = text(data.get("notes"), "Notes", 500)

    # IMMEDIATE takes the write lock up front, so two people can't grab the same slot.
    conn.execute("BEGIN IMMEDIATE")
    try:
        if start not in available_times(conn, day, service["duration_min"], datetime.now()):
            raise ApiError(409, "Sorry, that time was just taken. Please pick another one.")
        code = unique_code(conn)
        conn.execute(
            """INSERT INTO appointments (code, service_id, start_at, end_at, price_cents,
                                         customer_name, phone, email, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, service["id"], fmt_dt(start), fmt_dt(end), service["price_cents"],
             name, phone, email, notes, fmt_dt(datetime.now())),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return 201, {
        "code": code,
        "service": service["name"],
        "duration_min": service["duration_min"],
        "price_cents": service["price_cents"],
        "start": fmt_dt(start),
        "end": fmt_dt(end),
        "name": name,
    }


# ---------------------------------------------------------------- admin API


def is_admin(req) -> bool:
    token = req.cookies.get(SESSION_COOKIE)
    expiry = _sessions.get(token) if token else None
    if expiry is None:
        return False
    if expiry < time.time():
        _sessions.pop(token, None)
        return False
    return True


@route("GET", "/api/admin/session")
def admin_session(req):
    return {"authenticated": is_admin(req)}


@route("POST", "/api/admin/login")
def admin_login(req):
    password = req.body.get("password")
    if not isinstance(password, str) or not secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
        time.sleep(0.5)
        raise ApiError(401, "That password isn't right.")
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_SECONDS
    req.set_cookies.append(
        f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}"
    )
    return {"authenticated": True}


@route("POST", "/api/admin/logout")
def admin_logout(req):
    _sessions.pop(req.cookies.get(SESSION_COOKIE, ""), None)
    req.set_cookies.append(f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
    return {"authenticated": False}


@route("GET", "/api/admin/appointments", admin=True)
def admin_appointments(req):
    now = fmt_dt(datetime.now())
    query = """SELECT a.*, s.name AS service_name FROM appointments a
               JOIN services s ON s.id = a.service_id"""
    if req.arg("scope") == "past":
        rows = req.conn.execute(query + " WHERE a.end_at < ? ORDER BY a.start_at DESC LIMIT 200", (now,))
    else:
        rows = req.conn.execute(query + " WHERE a.end_at >= ? AND a.status = 'booked' ORDER BY a.start_at", (now,))
    return [appointment_dict(row) for row in rows]


@route("POST", r"/api/admin/appointments/(?P<id>\d+)/cancel", admin=True)
def admin_cancel_appointment(req):
    cursor = req.conn.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = ? AND status = 'booked'", (int(req.params["id"]),)
    )
    if cursor.rowcount == 0:
        raise ApiError(404, "That appointment was not found or is already cancelled.")
    return {"ok": True}


@route("PUT", "/api/admin/hours", admin=True)
def admin_set_hours(req):
    days = req.body.get("days")
    if not isinstance(days, list) or len(days) != 7:
        raise ApiError(400, "Send hours for all 7 days.")
    rows = []
    for item in days:
        if not isinstance(item, dict):
            raise ApiError(400, "Each day must be an object.")
        weekday = integer(item.get("weekday"), "Weekday", 0, 6)
        is_open = bool(item.get("is_open"))
        open_time = parse_hhmm(item.get("open_time"), f"{WEEKDAYS[weekday]} opening time")
        close_time = parse_hhmm(item.get("close_time"), f"{WEEKDAYS[weekday]} closing time")
        if is_open and close_time <= open_time:
            raise ApiError(400, f"{WEEKDAYS[weekday]}: closing time must be after opening time.")
        rows.append((int(is_open), open_time.strftime("%H:%M"), close_time.strftime("%H:%M"), weekday))
    if sorted(row[3] for row in rows) != list(range(7)):
        raise ApiError(400, "Each day of the week must appear exactly once.")

    req.conn.execute("BEGIN")
    req.conn.executemany(
        "UPDATE weekly_hours SET is_open = ?, open_time = ?, close_time = ? WHERE weekday = ?", rows
    )
    req.conn.execute("COMMIT")
    return load_shop(req.conn)["hours"]


SHOP_TEXT_FIELDS = {
    "name": ("Shop name", 80, True),
    "tagline": ("Tagline", 160, False),
    "address": ("Address", 160, False),
    "city": ("City", 80, False),
    "parking": ("Parking notes", 300, False),
    "phone": ("Phone", 30, False),
    "email": ("Email", 120, False),
    "instagram": ("Instagram", 60, False),
    "cancellation_policy": ("Cancellation policy", 400, False),
}
SHOP_INT_FIELDS = {
    "buffer_minutes": ("Buffer", 0, 60),
    "min_notice_minutes": ("Minimum notice", 0, 7 * 24 * 60),
    "max_days_ahead": ("Booking window", 1, 90),
}
SLOT_INTERVALS = (5, 10, 15, 20, 30, 60)


@route("PUT", "/api/admin/shop", admin=True)
def admin_update_shop(req):
    updates = {}
    for key, value in req.body.items():
        if key in SHOP_TEXT_FIELDS:
            label, max_len, required = SHOP_TEXT_FIELDS[key]
            updates[key] = text(value, label, max_len, required)
        elif key in SHOP_INT_FIELDS:
            label, low, high = SHOP_INT_FIELDS[key]
            updates[key] = integer(value, label, low, high)
        elif key == "slot_interval":
            if value not in SLOT_INTERVALS or isinstance(value, bool):
                raise ApiError(400, "Time slot spacing must be 5, 10, 15, 20, 30 or 60 minutes.")
            updates[key] = value
        elif key == "rules":
            if not isinstance(value, list) or len(value) > 20:
                raise ApiError(400, "Rules must be a list of up to 20 items.")
            updates[key] = json.dumps([rule for rule in (text(r, "Rule", 300) for r in value) if rule])
        else:
            raise ApiError(400, f"Unknown field: {key}")
    if updates:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        req.conn.execute(f"UPDATE shop SET {assignments} WHERE id = 1", list(updates.values()))
    return load_shop(req.conn)


@route("GET", "/api/admin/blocks", admin=True)
def admin_list_blocks(req):
    rows = req.conn.execute("SELECT * FROM blocks WHERE end_at > ? ORDER BY start_at", (fmt_dt(datetime.now()),))
    return [block_dict(row) for row in rows]


@route("POST", "/api/admin/blocks", admin=True)
def admin_add_block(req):
    data = req.body
    start_day = parse_date(data.get("start_date"), "Start date")
    end_day = parse_date(data.get("end_date") or data.get("start_date"), "End date")
    if data.get("all_day", True):
        start = datetime.combine(start_day, dtime.min)
        end = datetime.combine(end_day + timedelta(days=1), dtime.min)
    else:
        start = datetime.combine(start_day, parse_hhmm(data.get("start_time"), "Start time"))
        end = datetime.combine(end_day, parse_hhmm(data.get("end_time"), "End time"))
    if end <= start:
        raise ApiError(400, "Time off has to end after it starts.")
    reason = text(data.get("reason"), "Reason", 120)

    cursor = req.conn.execute(
        "INSERT INTO blocks (start_at, end_at, reason) VALUES (?, ?, ?)", (fmt_dt(start), fmt_dt(end), reason)
    )
    overlapping = req.conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status = 'booked' AND start_at < ? AND end_at > ?",
        (fmt_dt(end), fmt_dt(start)),
    ).fetchone()[0]
    row = req.conn.execute("SELECT * FROM blocks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return 201, {"block": block_dict(row), "overlapping_appointments": overlapping}


@route("DELETE", r"/api/admin/blocks/(?P<id>\d+)", admin=True)
def admin_delete_block(req):
    cursor = req.conn.execute("DELETE FROM blocks WHERE id = ?", (int(req.params["id"]),))
    if cursor.rowcount == 0:
        raise ApiError(404, "That time off was not found.")
    return {"ok": True}


@route("GET", "/api/admin/services", admin=True)
def admin_list_services(req):
    rows = req.conn.execute("SELECT * FROM services ORDER BY sort_order, id")
    return [service_dict(row) for row in rows]


def service_fields(data: dict, partial: bool) -> dict:
    fields = {}
    if not partial or "name" in data:
        fields["name"] = text(data.get("name"), "Name", 60, required=True)
    if not partial or "description" in data:
        fields["description"] = text(data.get("description"), "Description", 240)
    if not partial or "duration_min" in data:
        duration = integer(data.get("duration_min"), "Length", 5, 240)
        if duration % 5:
            raise ApiError(400, "Length must be in steps of 5 minutes.")
        fields["duration_min"] = duration
    if not partial or "price_cents" in data:
        fields["price_cents"] = integer(data.get("price_cents"), "Price", 0, 100000)
    if "active" in data:
        fields["active"] = int(bool(data["active"]))
    if "sort_order" in data:
        fields["sort_order"] = integer(data["sort_order"], "Order", 0, 1000)
    return fields


@route("POST", "/api/admin/services", admin=True)
def admin_add_service(req):
    fields = service_fields(req.body, partial=False)
    fields.setdefault("active", 1)
    if "sort_order" not in fields:
        highest = req.conn.execute("SELECT MAX(sort_order) FROM services").fetchone()[0]
        fields["sort_order"] = 0 if highest is None else highest + 1
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    cursor = req.conn.execute(f"INSERT INTO services ({columns}) VALUES ({placeholders})", list(fields.values()))
    return 201, load_service(req.conn, cursor.lastrowid, active_only=False)


@route("PUT", r"/api/admin/services/(?P<id>\d+)", admin=True)
def admin_update_service(req):
    service_id = int(req.params["id"])
    load_service(req.conn, service_id, active_only=False)
    fields = service_fields(req.body, partial=True)
    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        req.conn.execute(f"UPDATE services SET {assignments} WHERE id = ?", [*fields.values(), service_id])
    return load_service(req.conn, service_id, active_only=False)


# ------------------------------------------------------------------- server


class Handler(BaseHTTPRequestHandler):
    server_version = "Barbershop/0.1"

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def dispatch(self, method: str):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            if method != "GET":
                return self.send_json(405, {"error": "Method not allowed."})
            return self.serve_static(url.path)

        req = None
        try:
            fn, params, admin = self.match_route(method, url.path)
            body = self.read_body() if method in ("POST", "PUT") else {}
            conn = db.connect()
            try:
                req = Request(conn, params, parse_qs(url.query), body, self.read_cookies())
                if admin and not is_admin(req):
                    raise ApiError(401, "Please log in.")
                result = fn(req)
            finally:
                conn.close()
            status, payload = result if isinstance(result, tuple) else (200, result)
            self.send_json(status, payload, req.set_cookies)
        except ApiError as error:
            self.send_json(error.status, {"error": error.message})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "Something went wrong on our end. Please try again."})

    def match_route(self, method: str, path: str):
        path_matched = False
        for route_method, pattern, fn, admin in ROUTES:
            match = pattern.match(path)
            if match:
                path_matched = True
                if route_method == method:
                    return fn, match.groupdict(), admin
        raise ApiError(405 if path_matched else 404, "Method not allowed." if path_matched else "Not found.")

    def read_cookies(self) -> dict:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return {}
        return {key: morsel.value for key, morsel in cookie.items()}

    def read_body(self) -> dict:
        # Requiring JSON means a plain cross-site HTML form can't post to the API.
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ApiError(415, "Requests must be sent as JSON.")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "Request is too large.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw)
        except ValueError:
            raise ApiError(400, "Request body is not valid JSON.") from None
        if not isinstance(data, dict):
            raise ApiError(400, "Request body must be a JSON object.")
        return data

    def send_json(self, status: int, payload, cookies=()):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str):
        relative = PAGES.get(path.rstrip("/") or "/", path.lstrip("/"))
        file = (PUBLIC_DIR / relative).resolve()
        if PUBLIC_DIR not in file.parents or not file.is_file():
            file = PUBLIC_DIR / "404.html"
            status = 404
        else:
            status = 200
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "image/svg+xml":
            content_type += "; charset=utf-8"
        body = file.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"{self.log_date_time_string()}  {format % args}")


def main():
    conn = db.connect()
    db.init(conn)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.close()

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"\n  Barbershop site:  http://localhost:{port}")
    print(f"  Barber admin:     http://localhost:{port}/admin")
    if ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        print(f"  Admin password:   {DEFAULT_ADMIN_PASSWORD}  (set ADMIN_PASSWORD to change it)")
    print("\n  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
