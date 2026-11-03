import sqlite3

# Connect to sqlite
conn = sqlite3.connect("t3.db")
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

# Run SQL command to create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    time_spent REAL DEFAULT 0,
    time_stamp REAL,
    completed INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'normal',
    due_date TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
""")

# save
conn.commit()

# Insert rows in both tables
cursor.execute(
    "INSERT INTO projects (name) VALUES (?)",
    ("project1",)
)

project_id = cursor.lastrowid

cursor.execute("""
INSERT INTO tasks
(project_id, name, time_spent, completed, priority)
VALUES (?, ?, ?, ?, ?)
""", (project_id, "task1", 0, 0, "normal"))

cursor.execute("""
SELECT projects.name, tasks.name, tasks.completed, tasks.priority
FROM tasks
JOIN projects
ON tasks.project_id = projects.id
""")

print(cursor.fetchall())

conn.commit()
conn.close()