"""Tests for --complete, --delete, --start, --stop and --reopen.

Run from the repository folder:
    python -m unittest tests/test_zubair_commands.py -v

Every test uses a brand-new temporary folder and database built with the
team's init_db.py, so your real t3.db is never touched.
"""
import contextlib
import io
import os
import runpy
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


class CommandTests(unittest.TestCase):

    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        runpy.run_path(os.path.join(REPO, "init_db.py"))
        self.run_cmd(t3.t3Add, ["Study", "Read", "Write", "Review"])
        self.run_cmd(t3.t3Add, ["Gym"])  # gets the default 'maintask'

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    # helpers -------------------------------------------------------------
    def run_cmd(self, func, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = func(args)
        self.output = out.getvalue()
        return result

    def rows(self):
        conn = sqlite3.connect("t3.db")
        rows = conn.execute(
            "SELECT p.name, t.name, t.time_spent, t.time_stamp, t.completed "
            "FROM tasks t JOIN projects p ON t.project_id = p.id "
            "ORDER BY p.name, t.name").fetchall()
        conn.close()
        return rows

    def task(self, project, name):
        for r in self.rows():
            if r[0] == project and r[1] == name:
                return {"spent": r[2], "stamp": r[3], "done": r[4]}
        return None

    def projects(self):
        conn = sqlite3.connect("t3.db")
        names = [r[0] for r in conn.execute("SELECT name FROM projects")]
        conn.close()
        return sorted(names)

    # --complete ----------------------------------------------------------
    def test_complete_one_task_leaves_others(self):
        before = self.rows()
        self.assertTrue(self.run_cmd(t3.t3Complete, ["Study", "Read"]))
        self.assertEqual(self.task("Study", "Read")["done"], 1)
        changed = [a for a, b in zip(before, self.rows()) if a != b]
        self.assertEqual(len(changed), 1)

    def test_complete_whole_project(self):
        self.run_cmd(t3.t3Complete, ["Study"])
        for name in ("Read", "Write", "Review"):
            self.assertEqual(self.task("Study", name)["done"], 1)
        self.assertEqual(self.task("Gym", "maintask")["done"], 0)

    def test_complete_with_bad_name_changes_nothing(self):
        before = self.rows()
        self.assertFalse(self.run_cmd(t3.t3Complete, ["Study", "Read", "Nope"]))
        self.assertIn("Nope", self.output)
        self.assertEqual(before, self.rows())

    def test_complete_unknown_project(self):
        self.assertFalse(self.run_cmd(t3.t3Complete, ["Missing"]))
        self.assertIn("not found", self.output)

    def test_complete_no_args(self):
        self.assertFalse(self.run_cmd(t3.t3Complete, []))
        self.assertIn("required", self.output)

    def test_complete_twice_is_harmless(self):
        self.run_cmd(t3.t3Complete, ["Study", "Read"])
        self.run_cmd(t3.t3Complete, ["Study", "Read"])
        self.assertIn("already completed", self.output)

    def test_complete_stops_running_timer_and_keeps_time(self):
        self.run_cmd(t3.t3Start, ["Study", "Read"])
        with mock.patch("time.time", return_value=time.time() + 600):
            self.run_cmd(t3.t3Complete, ["Study", "Read"])
        t = self.task("Study", "Read")
        self.assertIsNone(t["stamp"])
        self.assertAlmostEqual(t["spent"], 10, delta=0.1)

    # --reopen ------------------------------------------------------------
    def test_reopen(self):
        self.run_cmd(t3.t3Complete, ["Study", "Read"])
        self.assertTrue(self.run_cmd(t3.t3Reopen, ["Study", "Read"]))
        self.assertEqual(self.task("Study", "Read")["done"], 0)

    # --delete ------------------------------------------------------------
    def test_delete_one_task(self):
        self.assertTrue(self.run_cmd(t3.t3Delete, ["Study", "Write"]))
        self.assertIsNone(self.task("Study", "Write"))
        self.assertIsNotNone(self.task("Study", "Read"))
        self.assertIn("Study", self.projects())

    def test_delete_project_removes_its_tasks_only(self):
        self.assertTrue(self.run_cmd(t3.t3Delete, ["Study"]))
        self.assertEqual(self.projects(), ["Gym"])
        self.assertEqual([r[0] for r in self.rows()], ["Gym"])

    def test_delete_bad_task_changes_nothing(self):
        before = self.rows()
        self.assertFalse(self.run_cmd(t3.t3Delete, ["Study", "Read", "Nope"]))
        self.assertEqual(before, self.rows())

    def test_delete_unknown_project(self):
        self.assertFalse(self.run_cmd(t3.t3Delete, ["Missing"]))
        self.assertEqual(len(self.projects()), 2)

    # --start / --stop ----------------------------------------------------
    def test_start_then_stop_adds_minutes(self):
        self.assertTrue(self.run_cmd(t3.t3Start, ["Study", "Read"]))
        self.assertIsNotNone(self.task("Study", "Read")["stamp"])
        with mock.patch("time.time", return_value=time.time() + 90 * 60):
            self.assertTrue(self.run_cmd(t3.t3Stop, ["Study", "Read"]))
        t = self.task("Study", "Read")
        self.assertIsNone(t["stamp"])
        self.assertAlmostEqual(t["spent"], 90, delta=0.1)

    def test_two_sessions_add_up(self):
        for _ in range(2):
            self.run_cmd(t3.t3Start, ["Study", "Read"])
            with mock.patch("time.time", return_value=time.time() + 300):
                self.run_cmd(t3.t3Stop, ["Study", "Read"])
        self.assertAlmostEqual(self.task("Study", "Read")["spent"], 10, delta=0.1)

    def test_start_twice_does_not_reset_timer(self):
        self.run_cmd(t3.t3Start, ["Study", "Read"])
        first = self.task("Study", "Read")["stamp"]
        self.assertFalse(self.run_cmd(t3.t3Start, ["Study", "Read"]))
        self.assertIn("already running", self.output)
        self.assertEqual(first, self.task("Study", "Read")["stamp"])

    def test_stop_without_start(self):
        self.assertFalse(self.run_cmd(t3.t3Stop, ["Study", "Read"]))
        self.assertIn("No running timer", self.output)
        self.assertEqual(self.task("Study", "Read")["spent"], 0)

    def test_start_single_task_project_without_task_name(self):
        self.assertTrue(self.run_cmd(t3.t3Start, ["Gym"]))
        self.assertIsNotNone(self.task("Gym", "maintask")["stamp"])

    def test_start_multi_task_project_needs_task_name(self):
        self.assertFalse(self.run_cmd(t3.t3Start, ["Study"]))
        self.assertIn("name one", self.output)

    def test_start_completed_task_refused(self):
        self.run_cmd(t3.t3Complete, ["Study", "Read"])
        self.assertFalse(self.run_cmd(t3.t3Start, ["Study", "Read"]))
        self.assertIn("--reopen", self.output)

    def test_stop_project_stops_all_its_timers(self):
        self.run_cmd(t3.t3Start, ["Study", "Read"])
        self.run_cmd(t3.t3Start, ["Study", "Write"])
        self.assertTrue(self.run_cmd(t3.t3Stop, ["Study"]))
        self.assertIsNone(self.task("Study", "Read")["stamp"])
        self.assertIsNone(self.task("Study", "Write")["stamp"])

    # works with teammates' features ---------------------------------------
    def test_running_display_sees_started_timer(self):
        self.run_cmd(t3.t3Start, ["Study", "Read"])
        self.run_cmd(t3.t3Running, [])
        self.assertIn("Read", self.output)
        self.run_cmd(t3.t3Stop, ["Study", "Read"])
        self.run_cmd(t3.t3Running, [])
        self.assertIn("No timers", self.output)

    def test_progress_and_pending_reflect_completion(self):
        self.run_cmd(t3.t3Complete, ["Study", "Read"])
        self.run_cmd(t3.t3Progress, [])
        self.assertIn("33%", self.output)
        self.run_cmd(t3.t3Pending, [])
        self.assertNotIn("Task: Read", self.output)

    # real command line ---------------------------------------------------
    def test_command_line(self):
        script = os.path.join(REPO, "t3.py")
        for args in (["--start", "Study", "Read"], ["--stop", "Study", "Read"],
                     ["--complete", "Study", "Read"], ["--delete", "Gym"]):
            p = subprocess.run([sys.executable, script] + args,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(self.task("Study", "Read")["done"], 1)
        self.assertEqual(self.projects(), ["Study"])


if __name__ == "__main__":
    unittest.main()
