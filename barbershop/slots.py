"""Works out which appointment start times are free on a given day."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta

DT_FORMAT = "%Y-%m-%dT%H:%M"


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, DT_FORMAT)


def fmt_dt(value: datetime) -> str:
    return value.strftime(DT_FORMAT)


def _at(day: date, hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hour, minute))


def open_slots(
    day: date,
    duration_min: int,
    open_time: str,
    close_time: str,
    appointments: list[tuple[datetime, datetime]],
    blocks: list[tuple[datetime, datetime]],
    *,
    buffer_min: int,
    interval_min: int,
    earliest: datetime,
) -> list[datetime]:
    """Start times on `day` where a `duration_min` cut fits inside opening hours.

    Every cut (booked or proposed) is followed by `buffer_min` of cleanup time,
    so two cuts never sit closer together than the buffer. Blocks (time off)
    are hard edges with no buffer. Times before `earliest` are skipped.
    """
    open_at = _at(day, open_time)
    close_at = _at(day, close_time)
    duration = timedelta(minutes=duration_min)
    buffer = timedelta(minutes=buffer_min)
    step = timedelta(minutes=interval_min)

    slots = []
    start = open_at
    while start + duration <= close_at:
        end = start + duration
        clashes_appointment = any(
            start < booked_end + buffer and booked_start < end + buffer
            for booked_start, booked_end in appointments
        )
        clashes_block = any(start < block_end and block_start < end for block_start, block_end in blocks)
        if start >= earliest and not clashes_appointment and not clashes_block:
            slots.append(start)
        start += step
    return slots


def available_times(conn: sqlite3.Connection, day: date, duration_min: int, now: datetime) -> list[datetime]:
    """Bookable start times for a service of `duration_min` on `day`, using the shop's live data."""
    shop = conn.execute(
        "SELECT buffer_minutes, slot_interval, min_notice_minutes, max_days_ahead FROM shop WHERE id = 1"
    ).fetchone()
    if day < now.date() or day > now.date() + timedelta(days=shop["max_days_ahead"]):
        return []

    hours = conn.execute(
        "SELECT is_open, open_time, close_time FROM weekly_hours WHERE weekday = ?", (day.weekday(),)
    ).fetchone()
    if hours is None or not hours["is_open"]:
        return []

    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)
    appointments = [
        (parse_dt(row["start_at"]), parse_dt(row["end_at"]))
        for row in conn.execute(
            "SELECT start_at, end_at FROM appointments WHERE status = 'booked' AND start_at < ? AND end_at > ?",
            (fmt_dt(day_end), fmt_dt(day_start - timedelta(minutes=shop["buffer_minutes"]))),
        )
    ]
    blocks = [
        (parse_dt(row["start_at"]), parse_dt(row["end_at"]))
        for row in conn.execute(
            "SELECT start_at, end_at FROM blocks WHERE start_at < ? AND end_at > ?",
            (fmt_dt(day_end), fmt_dt(day_start)),
        )
    ]
    return open_slots(
        day,
        duration_min,
        hours["open_time"],
        hours["close_time"],
        appointments,
        blocks,
        buffer_min=shop["buffer_minutes"],
        interval_min=shop["slot_interval"],
        earliest=now + timedelta(minutes=shop["min_notice_minutes"]),
    )


def day_status(conn: sqlite3.Connection, day: date, duration_min: int, now: datetime) -> str:
    """'closed' if the shop doesn't work that weekday, 'open' if any time is free, else 'full'."""
    hours = conn.execute("SELECT is_open FROM weekly_hours WHERE weekday = ?", (day.weekday(),)).fetchone()
    if hours is None or not hours["is_open"]:
        return "closed"
    return "open" if available_times(conn, day, duration_min, now) else "full"
