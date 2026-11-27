"""Tests for --timesheet and session logging (Zubair).

Run: python -m unittest discover -s tests
Each test uses its own temporary database through T3_DB.
"""
import contextlib
import datetime
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import t3  # noqa: E402


def at(days_ago, hour, minute=0):
    """Unix time for HH:MM local time, N days ago."""
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return time.mktime(datetime.datetime(day.year, day.month, day.day,
                                         hour, minute).timetuple())


class TimesheetTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "t3.db")
        os.environ["T3_DB"] = self.db
        self.addCleanup(os.environ.pop, "T3_DB", None)
        self.cmd(t3.t3Add, ["Website", "Design", "Build"])
        self.cmd(t3.t3Add, ["Thesis", "Write"])

    def cmd(self, func, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = func(args)
        self.output = out.getvalue()
        return result

    def work(self, project, task, start, minutes):
        """Simulate --start at `start` and --stop `minutes` later."""
        with mock.patch("time.time", return_value=start):
            self.cmd(t3.t3Start, [project, task])
        with mock.patch("time.time", return_value=start + minutes * 60):
            self.cmd(t3.t3Stop, [project, task])

    def sessions(self):
        conn = sqlite3.connect(self.db)
        rows = conn.execute("SELECT task_id, minutes FROM sessions").fetchall()
        conn.close()
        return rows

    # session logging -------------------------------------------------------
    def test_stop_logs_a_session(self):
        self.work("Website", "Design", at(0, 9), 90)
        rows = self.sessions()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0][1], 90, delta=0.1)

    def test_complete_with_running_timer_logs_a_session(self):
        with mock.patch("time.time", return_value=at(0, 9)):
            self.cmd(t3.t3Start, ["Website", "Design"])
        with mock.patch("time.time", return_value=at(0, 9, 30)):
            self.cmd(t3.t3Complete, ["Website", "Design"])
        self.assertAlmostEqual(self.sessions()[0][1], 30, delta=0.1)

    def test_deleting_task_or_project_removes_its_sessions(self):
        self.work("Website", "Design", at(0, 9), 60)
        self.work("Thesis", "Write", at(0, 11), 60)
        self.cmd(t3.t3Delete, ["Website", "Design"])
        self.assertEqual(len(self.sessions()), 1)
        self.cmd(lambda a: t3.t3Delete(a, assume_yes=True), ["Thesis"])
        self.assertEqual(self.sessions(), [])

    def test_clear_completed_still_works_with_sessions(self):
        self.work("Website", "Design", at(0, 9), 60)
        self.cmd(t3.t3Complete, ["Website", "Design"])
        self.cmd(t3.t3ClearCompleted, [])
        self.assertEqual(self.sessions(), [])

    # timesheet output ------------------------------------------------------
    def test_week_timesheet_totals(self):
        self.work("Website", "Design", at(0, 9), 90)
        self.work("Website", "Build", at(0, 13), 30)
        self.work("Website", "Design", at(2, 10), 60)
        self.work("Thesis", "Write", at(2, 14), 45)
        self.assertTrue(self.cmd(t3.t3Timesheet, []))
        out = self.output
        self.assertIn("Last 7 Days", out)
        website = next(l for l in out.splitlines() if l.startswith("Website"))
        self.assertTrue(website.rstrip().endswith("3h 00m"), website)
        total = [l for l in out.splitlines() if l.startswith("Total")][-1]
        self.assertTrue(total.rstrip().endswith("3h 45m"), total)

    def test_today_excludes_older_days(self):
        self.work("Website", "Design", at(0, 9), 20)
        self.work("Thesis", "Write", at(3, 9), 50)
        self.cmd(t3.t3Timesheet, ["today"])
        self.assertIn("Website", self.output)
        self.assertNotIn("Thesis", self.output)

    def test_week_excludes_older_than_seven_days(self):
        self.work("Thesis", "Write", at(10, 9), 50)
        self.cmd(t3.t3Timesheet, ["week"])
        self.assertIn("No time logged", self.output)
        self.cmd(t3.t3Timesheet, ["30"])
        self.assertIn("Thesis", self.output)

    def test_project_filter(self):
        self.work("Website", "Design", at(0, 9), 20)
        self.work("Thesis", "Write", at(0, 11), 50)
        self.cmd(t3.t3Timesheet, ["week", "Thesis"])
        self.assertIn("Thesis", self.output)
        self.assertNotIn("Website", self.output.split("---\n", 1)[1])

    def test_mentions_running_timers(self):
        self.work("Website", "Design", at(0, 9), 20)
        self.cmd(t3.t3Start, ["Thesis", "Write"])
        self.cmd(t3.t3Timesheet, [])
        self.assertIn("still running", self.output)

    def test_bad_period(self):
        self.assertFalse(self.cmd(t3.t3Timesheet, ["lots"]))
        self.assertIn("Error", self.output)

    def test_format_minutes(self):
        self.assertEqual(t3.format_minutes(0), "0m")
        self.assertEqual(t3.format_minutes(45), "45m")
        self.assertEqual(t3.format_minutes(90.4), "1h 30m")
        self.assertEqual(t3.format_minutes(605), "10h 05m")

    def test_command_line(self):
        self.work("Website", "Design", at(0, 9), 15)
        p = subprocess.run([sys.executable, os.path.join(REPO, "t3.py"),
                            "--timesheet"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("15m", p.stdout)

    def test_existing_database_gets_sessions_table(self):
        # A database made before this feature has no sessions table;
        # opening it with the new code must add it without losing data.
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE sessions")
        conn.commit()
        conn.close()
        self.cmd(t3.t3Report, ["all"])
        self.assertIn("Design", self.output)
        self.work("Website", "Design", at(0, 9), 10)
        self.assertEqual(len(self.sessions()), 1)


if __name__ == "__main__":
    unittest.main()
