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
    tags TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
""")

cursor.execute("PRAGMA table_info(tasks)")
columns = [row[1] for row in cursor.fetchall()]

if "tags" not in columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN tags TEXT")



conn.commit()
conn.close()