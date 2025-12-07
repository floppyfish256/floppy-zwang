import sqlite3
from pathlib import Path

# Use a db filename relative to the project directory; adjust if needed
DB_FILENAME = str(Path(__file__).resolve().parent.joinpath("../tasks.db"))


def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            priority INTEGER DEFAULT 0,
            tags TEXT,
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS gc_mapping (
            task_id INTEGER UNIQUE,
            gc_event_id TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
        """
    )
    conn.commit()
    conn.close()


def db_get_connection():
    return sqlite3.connect(DB_FILENAME)


def add_task(title, description="", due_date=None, priority=0, tags=""):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO tasks (title, description, due_date, priority, tags, completed)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (title, description, due_date, priority, tags),
    )
    conn.commit()
    tid = c.lastrowid
    conn.close()
    return tid


def update_task(task_id, title, description, due_date, priority, tags, completed):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE tasks SET title=?, description=?, due_date=?, priority=?, tags=?, completed=?,
        updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (title, description, due_date, priority, tags, completed, task_id),
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    c.execute("DELETE FROM gc_mapping WHERE task_id=?", (task_id,))
    conn.commit()
    conn.close()


def get_tasks(filter_tag=None, show_completed=False, sort_by="due_date"):
    conn = db_get_connection()
    c = conn.cursor()
    q = "SELECT id, title, description, due_date, priority, tags, completed FROM tasks"
    args = []
    where = []
    if not show_completed:
        where.append("completed=0")
    if filter_tag:
        where.append("tags LIKE ?")
        args.append(f"%{filter_tag}%")
    if where:
        q += " WHERE " + " AND ".join(where)

    if sort_by == "priority":
        q += " ORDER BY priority DESC, due_date IS NULL, due_date ASC"
    elif sort_by == "title":
        q += " ORDER BY title COLLATE NOCASE ASC"
    else:
        q += " ORDER BY (due_date IS NULL), due_date ASC"

    c.execute(q, args)
    rows = c.fetchall()
    conn.close()
    return rows


def get_task(task_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, description, due_date, priority, tags, completed FROM tasks WHERE id=?",
        (task_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def map_task_to_gc(task_id, event_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO gc_mapping (task_id, gc_event_id) VALUES (?, ?)",
        (task_id, event_id),
    )
    conn.commit()
    conn.close()


def get_gc_event_id(task_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("SELECT gc_event_id FROM gc_mapping WHERE task_id=?", (task_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None
