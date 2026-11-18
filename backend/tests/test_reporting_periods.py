import unittest
from datetime import datetime, timezone

from app.services.reservations import reporting_bounds


class ReportingPeriodTests(unittest.TestCase):
    def test_paris_march_includes_late_february_utc_check_in(self):
        start, end = reporting_bounds(2024, 3, "Europe/Paris")
        check_in = datetime(2024, 2, 29, 23, 30, tzinfo=timezone.utc)
        self.assertLessEqual(start, check_in)
        self.assertLess(check_in, end)
        self.assertEqual(start.isoformat(), "2024-02-29T23:00:00+00:00")
        self.assertEqual(end.isoformat(), "2024-03-31T22:00:00+00:00")

    def test_new_york_boundary_and_daylight_saving(self):
        start, end = reporting_bounds(2024, 3, "America/New_York")
        self.assertEqual(start.isoformat(), "2024-03-01T05:00:00+00:00")
        self.assertEqual(end.isoformat(), "2024-04-01T04:00:00+00:00")

    def test_december_rolls_into_next_year(self):
        start, end = reporting_bounds(2024, 12, "Europe/Paris")
        self.assertEqual(start.isoformat(), "2024-11-30T23:00:00+00:00")
        self.assertEqual(end.isoformat(), "2024-12-31T23:00:00+00:00")

    def test_annual_period_uses_local_year(self):
        start, end = reporting_bounds(2024, None, "America/New_York")
        self.assertEqual(start.isoformat(), "2024-01-01T05:00:00+00:00")
        self.assertEqual(end.isoformat(), "2025-01-01T05:00:00+00:00")
