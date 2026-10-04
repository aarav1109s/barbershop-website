import unittest
from datetime import date, datetime, timedelta

from barbershop import db
from barbershop.slots import available_times, day_status, fmt_dt, open_slots

DAY = date(2026, 10, 5)  # a Monday


def at(hhmm: str, day: date = DAY) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute)


def times(slots):
    return [slot.strftime("%H:%M") for slot in slots]


class OpenSlotsTest(unittest.TestCase):
    def slots(self, duration=30, appointments=(), blocks=(), buffer=0, interval=15, earliest=None):
        return times(
            open_slots(
                DAY,
                duration,
                "10:00",
                "12:00",
                list(appointments),
                list(blocks),
                buffer_min=buffer,
                interval_min=interval,
                earliest=earliest or at("00:00"),
            )
        )

    def test_empty_day_fills_opening_hours(self):
        self.assertEqual(self.slots(), ["10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30"])

    def test_cut_must_finish_before_closing(self):
        self.assertEqual(self.slots(duration=60, interval=30), ["10:00", "10:30", "11:00"])

    def test_booked_appointment_and_buffer_are_skipped(self):
        booked = [(at("10:30"), at("11:00"))]
        self.assertEqual(self.slots(appointments=booked, buffer=10), ["11:15", "11:30"])

    def test_back_to_back_allowed_without_buffer(self):
        booked = [(at("10:30"), at("11:00"))]
        self.assertEqual(self.slots(appointments=booked), ["10:00", "11:00", "11:15", "11:30"])

    def test_blocks_are_hard_edges(self):
        self.assertEqual(self.slots(blocks=[(at("11:00"), at("12:00"))], buffer=10), ["10:00", "10:15", "10:30"])

    def test_minimum_notice_skips_early_times(self):
        self.assertEqual(self.slots(earliest=at("11:05")), ["11:15", "11:30"])


class AvailableTimesTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init(self.conn)
        self.conn.execute("UPDATE shop SET buffer_minutes = 0, slot_interval = 30, min_notice_minutes = 60")
        self.now = at("08:00")

    def tearDown(self):
        self.conn.close()

    def test_uses_weekly_hours(self):
        result = times(available_times(self.conn, DAY, 60, self.now))
        self.assertEqual(result[0], "10:00")
        self.assertEqual(result[-1], "17:00")

    def test_closed_weekday(self):
        sunday = DAY + timedelta(days=6)
        self.assertEqual(available_times(self.conn, sunday, 30, self.now), [])
        self.assertEqual(day_status(self.conn, sunday, 30, self.now), "closed")

    def test_past_and_too_far_ahead_are_empty(self):
        self.assertEqual(available_times(self.conn, DAY - timedelta(days=1), 30, self.now), [])
        self.assertEqual(available_times(self.conn, DAY + timedelta(days=60), 30, self.now), [])

    def test_cancelled_appointments_free_the_slot(self):
        self.conn.execute(
            """INSERT INTO appointments (code, service_id, start_at, end_at, price_cents, customer_name,
                                         phone, status, created_at)
               VALUES ('AAAAAA', 1, ?, ?, 3500, 'Sam', '5551234567', 'cancelled', ?)""",
            (fmt_dt(at("10:00")), fmt_dt(at("10:30")), fmt_dt(self.now)),
        )
        self.assertIn("10:00", times(available_times(self.conn, DAY, 30, self.now)))

    def test_full_day_block_marks_day_full(self):
        self.conn.execute(
            "INSERT INTO blocks (start_at, end_at) VALUES (?, ?)",
            (fmt_dt(at("00:00")), fmt_dt(at("00:00", DAY + timedelta(days=1)))),
        )
        self.assertEqual(day_status(self.conn, DAY, 30, self.now), "full")


if __name__ == "__main__":
    unittest.main()
