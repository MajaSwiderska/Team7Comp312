#!/usr/bin/env python3
import argparse
import time
import datetime
import os
import json
import sqlite3

"""time tracker and to do list, T3. Todo list where you can add your tasks, keep track of how long you have been working on them, and save your output to a text file for additional scripting"""
"""T3 is to assist those who struggle with time management through a simple, easy to use to do list time tracker """

def get_db_connection():
    conn = sqlite3.connect("t3.db")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ---------------------------------------------------------------------------
# Zubair: --complete, --delete, --start, --stop (and --reopen), using SQLite.
# Time is stored in MINUTES so it matches --summary, --edit and --running.
# ---------------------------------------------------------------------------

def _get_project_id(cursor, project_name):
    """Return the id of the project with this name, or None."""
    cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
    row = cursor.fetchone()
    return row[0] if row else None


def _get_tasks(cursor, project_id, task_names=None):
    """Return {task_name: (id, time_spent, time_stamp, completed)}.

    With task_names, only those tasks are returned, plus a list of the
    names that were not found. Without it, every task in the project.
    """
    cursor.execute(
        "SELECT name, id, time_spent, time_stamp, completed "
        "FROM tasks WHERE project_id = ?",
        (project_id,)
    )
    all_tasks = {row[0]: row[1:] for row in cursor.fetchall()}
    if not task_names:
        return all_tasks, []
    found = {n: all_tasks[n] for n in task_names if n in all_tasks}
    missing = [n for n in task_names if n not in all_tasks]
    return found, missing


def _resolve(cursor, arglist, usage):
    """Shared input checks for my commands.

    Returns (project_id, tasks_dict) or None after printing an error.
    Nothing is changed in the database if any name is wrong.
    """
    if not arglist:
        print(f"Error: project name required. Usage: {usage}")
        return None
    project_name, task_names = arglist[0], arglist[1:]
    project_id = _get_project_id(cursor, project_name)
    if project_id is None:
        print(f"Error: project '{project_name}' not found.")
        return None
    tasks, missing = _get_tasks(cursor, project_id, task_names)
    if missing:
        print(f"Error: task(s) not found in '{project_name}': "
              + ", ".join(missing) + ". No changes made.")
        return None
    return project_id, tasks


def _is_running(time_stamp):
    return time_stamp is not None and time_stamp != 0


def _elapsed_minutes(time_stamp):
    return round((time.time() - float(time_stamp)) / 60, 2)


def t3Complete(arglist):
    # t3 --complete projectName [task1 task2 ...]
    # No task names = complete every task in the project.
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        found = _resolve(cursor, arglist, "t3 --complete project [task ...]")
        if found is None:
            return False
        _, tasks = found
        if not tasks:
            print(f"Project '{arglist[0]}' has no tasks to complete.")
            return False
        for name, (task_id, spent, stamp, done) in tasks.items():
            if done:
                print(f"Task '{name}' is already completed.")
                continue
            if _is_running(stamp):
                # Finishing a task also stops its timer, so the time is kept.
                spent = (spent or 0) + _elapsed_minutes(stamp)
                print(f"Stopped running timer on '{name}'.")
            cursor.execute(
                "UPDATE tasks SET completed = 1, time_stamp = NULL, "
                "time_spent = ? WHERE id = ?",
                (round(spent or 0, 2), task_id)
            )
            print(f"Completed task '{name}' in project '{arglist[0]}'.")
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error, no changes made: {e}")
        return False
    finally:
        conn.close()


def t3Reopen(arglist):
    # t3 --reopen projectName [task1 task2 ...]
    # Opposite of --complete: marks tasks as not completed again.
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        found = _resolve(cursor, arglist, "t3 --reopen project [task ...]")
        if found is None:
            return False
        _, tasks = found
        for name, (task_id, _, _, done) in tasks.items():
            if not done:
                print(f"Task '{name}' is not completed.")
                continue
            cursor.execute("UPDATE tasks SET completed = 0 WHERE id = ?",
                           (task_id,))
            print(f"Reopened task '{name}' in project '{arglist[0]}'.")
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error, no changes made: {e}")
        return False
    finally:
        conn.close()


def t3Delete(arglist):
    # t3 --delete projectName            -> delete project and all its tasks
    # t3 --delete projectName task1 ...  -> delete only those tasks
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        found = _resolve(cursor, arglist, "t3 --delete project [task ...]")
        if found is None:
            return False
        project_id, tasks = found
        if len(arglist) > 1:
            for name, (task_id, *_rest) in tasks.items():
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                print(f"Deleted task '{name}' from project '{arglist[0]}'.")
        else:
            # Tasks first: the foreign key does not allow orphan tasks.
            cursor.execute("DELETE FROM tasks WHERE project_id = ?",
                           (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            print(f"Deleted project '{arglist[0]}' and its "
                  f"{len(tasks)} task(s).")
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error, no changes made: {e}")
        return False
    finally:
        conn.close()


def _pick_one_task(arglist, tasks, command):
    """--start needs exactly one task. If the project has only one task
    (for example the default 'maintask'), use it."""
    if len(arglist) > 2:
        print(f"Error: {command} takes one task at a time.")
        return None
    if len(arglist) == 2:
        return arglist[1]
    if len(tasks) == 1:
        return next(iter(tasks))
    if not tasks:
        print(f"Error: project '{arglist[0]}' has no tasks.")
    else:
        print(f"Error: project '{arglist[0]}' has several tasks, name one: "
              + ", ".join(tasks))
    return None


def t3Start(arglist):
    # t3 --start projectName [task]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        found = _resolve(cursor, arglist, "t3 --start project [task]")
        if found is None:
            return False
        _, tasks = found
        name = _pick_one_task(arglist, tasks, "--start")
        if name is None:
            return False
        task_id, _, stamp, done = tasks[name]
        if done:
            print(f"Error: task '{name}' is completed. "
                  f"Use --reopen first to track more time.")
            return False
        if _is_running(stamp):
            print(f"Timer for '{name}' is already running "
                  f"({_elapsed_minutes(stamp)} minutes so far).")
            return False
        cursor.execute("UPDATE tasks SET time_stamp = ? WHERE id = ?",
                       (time.time(), task_id))
        conn.commit()
        print(f"Started timer for '{name}' in project '{arglist[0]}'.")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error, no changes made: {e}")
        return False
    finally:
        conn.close()


def t3Stop(arglist):
    # t3 --stop projectName [task]
    # Without a task name, stops every running timer in the project.
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        found = _resolve(cursor, arglist, "t3 --stop project [task]")
        if found is None:
            return False
        _, tasks = found
        running = {n: t for n, t in tasks.items() if _is_running(t[2])}
        if not running:
            print("No running timer to stop. Use --start first.")
            return False
        for name, (task_id, spent, stamp, _) in running.items():
            session = _elapsed_minutes(stamp)
            total = round((spent or 0) + session, 2)
            cursor.execute(
                "UPDATE tasks SET time_spent = ?, time_stamp = NULL "
                "WHERE id = ?",
                (total, task_id)
            )
            print(f"Stopped '{name}': {session} minutes this session, "
                  f"{total} minutes total.")
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error, no changes made: {e}")
        return False
    finally:
        conn.close()

def t3Report(arglist):
    # t3 --report active/completed/all

    if len(arglist) == 0:
        user_choice = "all"
    else:
        user_choice = arglist[0]

    conn = get_db_connection()
    cursor = conn.cursor()

    if user_choice == "all":

        cursor.execute("""
            SELECT
                projects.name,
                tasks.name,
                tasks.time_spent,
                tasks.completed
            FROM tasks
            JOIN projects
                ON tasks.project_id = projects.id
            ORDER BY projects.name
        """)

    elif user_choice == "active":

        cursor.execute("""
            SELECT
                projects.name,
                tasks.name,
                tasks.time_spent,
                tasks.completed
            FROM tasks
            JOIN projects
                ON tasks.project_id = projects.id
            WHERE tasks.completed = 0
            ORDER BY projects.name
        """)

    elif user_choice == "completed":

        cursor.execute("""
            SELECT
                projects.name,
                tasks.name,
                tasks.time_spent,
                tasks.completed
            FROM tasks
            JOIN projects
                ON tasks.project_id = projects.id
            WHERE tasks.completed = 1
            ORDER BY projects.name
        """)

    else:
        print(
            "Invalid option. "
            "Choose active/completed/all"
        )
        conn.close()
        return

    rows = cursor.fetchall()

    if not rows:
        print("No tasks found.")
        conn.close()
        return

    current_project = None

    for row in rows:
        project_name = row[0]
        task_name = row[1]
        time_spent = row[2]
        completed = row[3]

        if project_name != current_project:
            print(f"\nProject: {project_name}")
            current_project = project_name

        status = "completed" if completed else "not completed"

        print(
            f"    Task: {task_name} | "
            f"Time Spent: {time_spent} | "
            f"{status}"
        )

    conn.close()

# pld: returns (num_tasks_completed, num_tasks_total)
def completecount(tasklist):
    ccount = 0
    for t in tasklist:
        if t['completed']: ccount += 1
    return (ccount, len(tasklist))

# format of arglist: [projectName, taskname1, taskname2, ...]
# for existing projects, the new task(s) are added.
def t3Add(arglist):
    # t3 --add projectName task1 task2 ... taskN

    if len(arglist) == 0:
        print("Error: project name required")
        return

    project_name = arglist[0]
    task_names = arglist[1:]

    if len(task_names) == 0:
        task_names = ["maintask"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check whether project already exists
    cursor.execute(
        "SELECT id FROM projects WHERE name = ?",
        (project_name,)
    )

    row = cursor.fetchone()

    if row is None:
        # Project does not exist, so create it
        cursor.execute(
            "INSERT INTO projects (name) VALUES (?)",
            (project_name,)
        )

        project_id = cursor.lastrowid

    else:
        # Project already exists
        project_id = row[0]

    # Add tasks
    for task_name in task_names:

        cursor.execute(
            """
            SELECT id
            FROM tasks
            WHERE project_id = ? AND name = ?
            """,
            (project_id, task_name)
        )

        existing_task = cursor.fetchone()

        if existing_task:
            print(
                f"Error: project {project_name} "
                f"already has a task {task_name}"
            )

        else:
            cursor.execute(
                """
                INSERT INTO tasks
                (project_id, name, time_spent,
                 completed, priority)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, task_name, 0, 0, "normal")
            )

            print(
                f"Added task {task_name} "
                f"to project {project_name}"
            )

    conn.commit()
    conn.close()

# returns the (first) task in tlist with name equal to string tname, or None if not found

def findtask(tname, tlist):
   for t in tlist:
       if tname == t['taskName']: return t
   return None

# this is for debugging -- pld
def dumpdict(d):
   for k in d:
      print ('({}->{})'.format(k, d[k]))
   print

def dumpprojects(d):
   for proj in d:
      print ('{}: '.format(proj))
      for task in d[proj]:
         print('      {}'.format(str(task)))
      print

def t3Edit(arglist):
    #t3 --edit 'projectName'
    #needs to be able to check that user input the correct format
    if len(arglist) < 2:
        print("Error: Usage is t3 --edit [projectName] [taskName]")
        return
    
    projectName = arglist[0]
    taskName = arglist[1]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tasks.id, tasks.time_spent
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.name = ? AND tasks.name = ?
    """, (projectName, taskName))

    task = cursor.fetchone()

    if not task:
        print(f"Error: Task {taskName} not found in {projectName}.")
        conn.close()
        return

    task_id = task[0]
    print(f"Editing task: {taskName} (Current time: {task[1]}m)")

    newTime = input("Enter New Time In Minutes (or press Enter to skip): ")
    newPriority = input ("Enter Priority (High/Medium/Low, or press Enter to skip): ")
    newDue = input("Enter Due Date (e.g., 2026-11-01 or press Enter to skip): ")
    newTags = input("Enter Tags (comma separted or press Enter to skip): ")

    if newTime.strip():
        cursor.execute("UPDATE tasks SET time_spent = ? WHERE id = ?", (float(newTime), task_id))
    if newPriority.strip():
        cursor.execute("UPDATE tasks SET priority = ? WHERE id = ?", (newPriority, task_id))
    if newDue.strip():
        cursor.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (newDue, task_id))
    if newTags.strip(): # NEW
        cursor.execute("UPDATE tasks SET tags = ? WHERE id = ?", (newTags, task_id))

    conn.commit()
    print("Task updated successfully")
    conn.close()


# Maja Swiderska functions add
def t3Summary(arglist):
    #t3 --summary
    conn = get_db_connection()
    cursor = conn.cursor()
    print("\n--- Project Time Summary ---")

    cursor.execute("""
        SELECT projects.name, SUM(tasks.time_spent)
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        GROUP BY projects.id
    """)

    results = cursor.fetchall()
    total_time = 0
    for row in results:
            if row[1] and row[1] > 0:
                print(f"Project: {row[0]} | Total time: {row[1]} minutes")
                total_time += row[1]

    print("----------------------------")
    print(f"Total Time Tracked: {total_time} minutes\n")
    conn.close()

def t3Pending(arglist):
    #t3 --pending
    conn = get_db_connection()
    cursor = conn.cursor()
    print("\n--- Pending Tasks (Due Dates and Priorities, Tags) ---")

    cursor.execute("""
        SELECT projects.name, tasks.name, tasks.priority, tasks.due_date, tasks.tags
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE tasks.completed = 0
    """)

    pending = cursor.fetchall()
    if not pending:
        print("No pending tasks found")
    else:
        for row in pending:
            tags = row[4] if row[4] else "None"
            print(f"Project: {row[0]} | Task: {row[1]} | Priority: {row[2]} | Due: {row[3]} | Tags: {tags}")
    print("----------------------------------------------\n")
    conn.close()

def t3Search(arglist):
    if not arglist:
        print("Error: Please specify a tag to search for.")
        return

    search_term = arglist[0]
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"\n--- Search Results for Tag: '{search_term}' ---")

    cursor.execute("""
        SELECT projects.name, tasks.name, tasks.completed
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE tasks.tags LIKE ?
    """, (f'%{search_term}%',))

    results = cursor.fetchall()
    if not results:
        print("No tasks found with that tag.")
    else:
        for row in results:
            status = "completed" if row[2] else "pending"
            print(f"Project: {row[0]} | Task: {row[1]} | Status: {status}")

    print("----------------------------------------------\n")
    conn.close()

def t3Running(arglist):
    conn = get_db_connection()
    cursor = conn.cursor()

    print("\n--- Currently Running Timers ---")

    cursor.execute("""
        SELECT projects.name, tasks.name, tasks.time_stamp
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE tasks.time_stamp IS NOT NULL AND tasks.time_stamp != 0
    """)

    results = cursor.fetchall()
    if not results:
        print("No timers are currently running.")
    else:
        current_time = time.time()
        for row in results:
            start_time = float(row[2])
            elapsed_minutes = round((current_time - start_time) / 60, 2)
            print(f"Project: {row[0]} | Task: {row[1]} | Running for: {elapsed_minutes} minutes")

    print("--------------------------------\n")
    conn.close()

def t3Progress(arglist):
    conn = get_db_connection()
    cursor = conn.cursor()

    print("\n--- Project Progress ---")

    cursor.execute("""
        SELECT projects.name,
               COUNT(tasks.id) as total_tasks,
               SUM(CASE WHEN tasks.completed = 1 THEN 1 ELSE 0 END) as completed_tasks
        FROM projects
        LEFT JOIN tasks ON projects.id = tasks.project_id
        GROUP BY projects.id
    """)

    results = cursor.fetchall()
    for row in results:
        total = row[1]
        completed = row[2] if row[2] else 0

        if total > 0:
            percentage = int((completed / total) * 100)
            print(f"Project: {row[0]} | Progress: {percentage}%({completed} of {total} tasks done)")
        else:
            print(f"Project: {row[0]} | No tasks added yet.")

    print("------------------------\n")
    conn.close()

def t3ClearCompleted(arglist):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1")
    count = cursor.fetchone()[0]

    if count == 0:
        print("\nNo completed tasks to clear.")
    else:
        cursor.execute("DELETE FROM tasks WHERE completed = 1")
        conn.commit()
        print(f"\nSuccessfully cleared {count} completed task(s) from the database.")

    conn.close()

def _main():

    """Run the CLI Interface for T3"""
    #parser
    parser = argparse.ArgumentParser()
    
    parser.add_argument('userParserInput', nargs='*', help="the user input, will be printed if there are no arguments")
    
    parser.add_argument("--add",help="Adds a Project to your list",action='store_true', default=False, dest='addValue')
    parser.add_argument("--complete",help="Marks project on list as completed",action="store_true",default=False,dest="completeValue")
    parser.add_argument("--delete", help="Removes Project from list",action='store_true',default=False,dest='deleteValue')
    parser.add_argument("--report", help="Prints out basic report. Options: active/all/completed  (default=active)",action='store_true', default=False, dest='reportValue',)
    parser.add_argument("--start", help="Starts timing a task: t3 --start project [task]",action='store_true',default=False,dest='startValue')
    parser.add_argument("--stop", "--finish", help="Stops timing of a task, adds elapsed minutes to its total", action='store_true',default=False,dest="stopValue")
    parser.add_argument("--reopen", help="Marks completed task(s) as not completed again", action='store_true',default=False,dest="reopenValue")
    parser.add_argument("--edit", help="Edits the time spent on a Project (in minutes)", action='store_true',default=False,dest="editValue")
    parser.add_argument("--summary", action='store_true', default=False, dest='summaryValue')
    parser.add_argument("--pending", action='store_true', default=False, dest='pendingValue')
    parser.add_argument("--search", action='store_true', default=False, dest='searchValue')
    parser.add_argument("--running", action='store_true', default=False, dest='runningValue')
    parser.add_argument("--progress", action='store_true', default=False, dest='progressValue')
    parser.add_argument("--clear-completed", action='store_true', default=False, dest='clearValue')
    results = parser.parse_args()

    print('userParserInput='+str(results.userParserInput))	# pld

    if (results.reportValue) == True:
        t3Report(results.userParserInput)
    if (results.addValue) == True:
        t3Add(results.userParserInput)
    if (results.completeValue) == True:
        t3Complete(results.userParserInput)
    if (results.deleteValue) == True:
        t3Delete(results.userParserInput)
    if (results.editValue) == True:
        t3Edit(results.userParserInput)
    if (results.startValue) == True:
        t3Start(results.userParserInput)
    if (results.stopValue) == True:
        t3Stop(results.userParserInput)
    if (results.reopenValue) == True:
        t3Reopen(results.userParserInput)
    if (results.summaryValue) == True:
        t3Summary(results.userParserInput)
    if (results.pendingValue) == True:
        t3Pending(results.userParserInput)
    if (results.searchValue) == True:
        t3Search(results.userParserInput)
    if (results.runningValue) == True:
        t3Running(results.userParserInput)
    if (results.progressValue) == True:
        t3Progress(results.userParserInput)
    if (results.clearValue) == True:
        t3ClearCompleted(results.userParserInput)

if __name__ == '__main__':
    _main()

