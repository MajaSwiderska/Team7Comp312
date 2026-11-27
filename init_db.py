import os
import sqlite3

# Where T3 keeps its data.
# The professor's README asks for the data file to live in a fixed place
# in the user's home folder instead of wherever the program is run from.
#   Default:  ~/.t3/t3.db   (Windows: C:\Users\<you>\.t3\t3.db)
#   Override: set the T3_DB environment variable to another file path.


def db_path():
    path = os.environ.get("T3_DB")
    if not path:
        path = os.path.join(os.path.expanduser("~"), ".t3", "t3.db")
    return os.path.abspath(path)


def create_schema(conn):
    """Create the tables if they do not exist yet. Safe to run every time."""
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


def connect():
    """Open the T3 database, creating its folder and tables if needed."""
    path = db_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


if __name__ == "__main__":
    # Running "python init_db.py" still works; it now sets up the database
    # in the fixed location (t3.py also does this automatically).
    connect().close()
    print(f"T3 database ready at {db_path()}")
