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

def t3Complete(arglist):
    #t3 --complete 'activity'
    inputFile = 'tasks/tasks.json'
    jsonData=open(inputFile).read()
    data = json.loads(jsonData) 
    projectName = arglist[0]

    for k in data:
        if projectName == k['projectName']:
            k['completed'] = True

    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f)


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

def t3Delete(arglist):
    #t3 --delete 'activity'
    #removes activity when finished
    projectName=arglist[0]
    inputFile = 'tasks/tasks.json'
    jsonData=open(inputFile).read()
    data = json.loads(jsonData) 
    list1=[]
    for k in data:
        #print(type(k))
        if k['projectName'] == projectName:
            print("Found Project. Deleting.")
        else:
            list1.append(k)
    #print(list1)

    with open('tasks/tasks.json', 'w') as file:
                file.write(json.dumps(list1))


def t3Edit(arglist):
    #t3 --edit 'projectName'
    #needs to be able to check that user input the correct format
    projectName = arglist[0]
    inputFile = 'tasks/tasks.json'
    jsonData=open(inputFile).read()
    data = json.loads(jsonData) 

    for k in data:
        if projectName == k['projectName']:
            print("Current Time Is: " + str(k['timeSpent']))    
            newTime = input("Enter New Time In Minutes: ")
            #Converts user input of minutes to seconds
            k['timeSpent'] = float(newTime)

    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f)

def t3Start(arglist):
    #t3 --start 'projectName'
    projectName = arglist[0]
    inputFile = 'tasks/tasks.json'
    jsonData=open(inputFile).read()
    data = json.loads(jsonData)

    for k in data:
        if projectName == k['projectName']:
            print("Project Time Has Started")
            #currentTime = datetime.datetime.now().strftime('%H%M')
            k['timeStamp'] = time.time()
    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f)

def t3Stop(arglist):
    #t3 -- stop 'projectName'
    projectName = arglist[0]
    inputFile = 'tasks/tasks.json'
    jsonData=open(inputFile).read()
    data = json.loads(jsonData)

    for k in data:
        if projectName == k['projectName']:
            #check to make sure there is a timestamp
            if k['timeStamp'] == '':
                print("Project has no start time, is not being tracked")
                break
            print("Project Time Has Stopped, Tracked Time Updated")
            elapsedTime = time.time() - k['timeStamp']
            #add new time to current overall project time
            currentProjectTime = k['timeSpent']
            overallProjectTime = currentProjectTime + elapsedTime
            k['timeSpent'] = overallProjectTime
            k['timeStamp'] = ''
            print("Total Project Worktime: " + time.strftime("%H:%M:%S", time.gmtime(overallProjectTime)))
    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f)

# Maja Swiderska functions add
def t3Summary(arglist):
    #t3 --summary
    conn = get_db_connection()
    cursor = conn.cursor()
    print("\n--- Project Time Summary ---")

    cursor.execute("""
        SELECT projects.name, SUM(tasks.time_spent)
        FROM tasks
        JOIN projects ON tasks.project_id = project_id
        GROUP BY project.id
    """)

    results = cursor.fetchall()
    total_time = 0
    for row in results:
            if row[1] > 0:
                print(f"Project: {row[0]} | Total time: {row[1]} minutes")
                total_time += row[1]
    print("----------------------------")
    print(f"Total Time Tracked: {total_time} minutes\n")
    conn.close()

def t3Pending(arglist):
    #t3 --pending
    conn = get_db_connection()
    cursor = conn.cursor()
    print("\n--- Pending Tasks (Due Dates and Priorities) ---")

    cursor.execute("""
        SELECT projects.name, tasks.name, tasks.priority, tasks.due_date
        FROM tasks
        JOIN projects ON tasks.project_id = project.id
        WHERE tasks.completed = 0
    """)

    pending = cursor.fetchall()
    if not pending:
        print("No pending tasks found")
    else:
        for row in pending:
            print(f"Project: {row[0]} | Task: {row[1]} | Priority: {row[2]} | Due: {row[3]}")
        print("----------------------------------------------\n")
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
    parser.add_argument("--start", help="Starts timing of Project, will overwrite existing tracked time if project is already being tracked",action='store_true',default=False,dest='startValue')
    parser.add_argument("--stop/finish", help="Stops timing of Project, updates total run time", action='store_true',default=False,dest="stopValue")
    parser.add_argument("--edit", help="Edits the time spent on a Project (in minutes)", action='store_true',default=False,dest="editValue")
    results = parser.parse_args()

    print('userParserInput='+str(results.userParserInput))	# pld

    if (results.reportValue) == True:
        t3Report(results.userParserInput)
    if (results.addValue) == True:
        #t3Add(results.userParserInput)
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

if __name__ == '__main__':
    _main()

