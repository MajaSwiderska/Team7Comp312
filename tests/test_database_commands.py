import unittest
import sqlite3
import tempfile
import os
import sys
import runpy
import io
import contextlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import t3


class DatabaseTests(unittest.TestCase):

    def setUp(self):
        # Create an isolated database for each test
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, self.old_cwd)

        os.chdir(self.tmp.name)
        runpy.run_path(os.path.join(REPO, "init_db.py"))

    def execute_sql(self, query, params=()):
        conn = t3.get_db_connection()

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def run_command(self, func, args):
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            func(args)

        return output.getvalue()

    # Database tests

    def test_tables_created(self):
        rows = self.execute_sql("""
            SELECT name FROM sqlite_master
            WHERE type = 'table'
        """)

        tables = [row[0] for row in rows]

        self.assertIn("projects", tables)
        self.assertIn("tasks", tables)

    def test_tags_column_exists(self):
        rows = self.execute_sql("PRAGMA table_info(tasks)")
        columns = [row[1] for row in rows]

        self.assertIn("tags", columns)

    def test_foreign_key_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.execute_sql("""
                INSERT INTO tasks (project_id, name)
                VALUES (999, 'InvalidTask')
            """)

    def test_unique_task_constraint(self):
        self.run_command(t3.t3Add, ["School", "Homework"])

        project_id = self.execute_sql("""
            SELECT id FROM projects WHERE name = 'School'
        """)[0][0]

        with self.assertRaises(sqlite3.IntegrityError):
            self.execute_sql("""
                INSERT INTO tasks (project_id, name)
                VALUES (?, ?)
            """, (project_id, "Homework"))

    def test_schema_upgrade(self):
        # Simulate an older database without tags
        self.execute_sql("ALTER TABLE tasks DROP COLUMN tags")

        self.run_command(t3.t3Add, ["School", "Homework"])

        runpy.run_path(os.path.join(REPO, "init_db.py"))

        columns = self.execute_sql("PRAGMA table_info(tasks)")
        self.assertIn("tags", [row[1] for row in columns])

        rows = self.execute_sql("SELECT name FROM tasks")
        self.assertEqual(rows, [("Homework",)])

    def test_reinitialization_preserves_data(self):
        self.run_command(t3.t3Add, ["School", "Homework"])

        runpy.run_path(os.path.join(REPO, "init_db.py"))

        rows = self.execute_sql("SELECT name FROM tasks")
        self.assertEqual(rows, [("Homework",)])

    # Add command tests

    def test_add_project(self):
        self.run_command(t3.t3Add, ["School"])

        rows = self.execute_sql("SELECT name FROM projects")
        self.assertEqual(rows, [("School",)])

    def test_add_default_task(self):
        self.run_command(t3.t3Add, ["School"])

        rows = self.execute_sql("SELECT name FROM tasks")
        self.assertEqual(rows, [("maintask",)])

    def test_add_multiple_tasks(self):
        self.run_command(
            t3.t3Add, ["School", "Homework", "Presentation"]
        )

        rows = self.execute_sql("""
            SELECT name FROM tasks ORDER BY name
        """)

        self.assertEqual(
            rows, [("Homework",), ("Presentation",)]
        )

    def test_add_duplicate_task(self):
        self.run_command(t3.t3Add, ["School", "Homework"])
        self.run_command(t3.t3Add, ["School", "Homework"])

        rows = self.execute_sql("SELECT name FROM tasks")

        self.assertEqual(rows, [("Homework",)])

    def test_same_task_different_projects(self):
        self.run_command(t3.t3Add, ["School", "Homework"])
        self.run_command(t3.t3Add, ["Work", "Homework"])

        rows = self.execute_sql("""
            SELECT COUNT(*) FROM tasks
            WHERE name = 'Homework'
        """)

        self.assertEqual(rows[0][0], 2)

    def test_add_to_existing_project(self):
        self.run_command(t3.t3Add, ["School", "Homework"])
        self.run_command(t3.t3Add, ["School", "Presentation"])

        projects = self.execute_sql("SELECT COUNT(*) FROM projects")
        tasks = self.execute_sql("SELECT COUNT(*) FROM tasks")

        self.assertEqual(projects[0][0], 1)
        self.assertEqual(tasks[0][0], 2)

    # Report command tests

    def prepare_report_data(self):
        self.run_command(
            t3.t3Add, ["School", "Homework", "Presentation"]
        )

        self.execute_sql("""
            UPDATE tasks
            SET completed = 1, time_spent = 30
            WHERE name = 'Homework'
        """)

    def test_report_all(self):
        self.prepare_report_data()

        output = self.run_command(t3.t3Report, ["all"])

        self.assertIn("Homework", output)
        self.assertIn("Presentation", output)

    def test_report_active(self):
        self.prepare_report_data()

        output = self.run_command(t3.t3Report, ["active"])

        self.assertIn("Presentation", output)
        self.assertNotIn("Homework", output)

    def test_report_completed(self):
        self.prepare_report_data()

        output = self.run_command(t3.t3Report, ["completed"])

        self.assertIn("Homework", output)
        self.assertNotIn("Presentation", output)

    def test_report_default(self):
        self.prepare_report_data()

        default = self.run_command(t3.t3Report, [])
        explicit = self.run_command(t3.t3Report, ["all"])

        self.assertEqual(default, explicit)

    def test_report_invalid(self):
        output = self.run_command(t3.t3Report, ["invalid"])

        self.assertIn("Invalid option", output)

    def test_report_empty(self):
        output = self.run_command(t3.t3Report, ["all"])

        self.assertIn("No tasks found.", output)


if __name__ == "__main__":
    unittest.main()