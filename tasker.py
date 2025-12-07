"""
Minimalist Task Manager
"""

import os
import sqlite3
import datetime
import threading
import webbrowser
from tkinter import *
from tkinter import ttk, messagebox, simpledialog
try:
    from tkcalendar import DateEntry
    HAVE_TKCAL = True
except Exception:
    HAVE_TKCAL = False

# Google Calendar imports
try:
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import google.auth.exceptions
    import pickle
    HAVE_GOOGLE = True
except Exception:
    HAVE_GOOGLE = False

# -----------------------
# Database helpers
# -----------------------
DB_FILENAME = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,          -- ISO date YYYY-MM-DD
            priority INTEGER DEFAULT 0,
            tags TEXT,              -- comma-separated
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS gc_mapping (
            task_id INTEGER UNIQUE,
            gc_event_id TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)
    conn.commit()
    conn.close()

def db_get_connection():
    return sqlite3.connect(DB_FILENAME)

# CRUD
def add_task(title, description="", due_date=None, priority=0, tags=""):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tasks (title, description, due_date, priority, tags, completed)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (title, description, due_date, priority, tags))
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return task_id

def update_task(task_id, title, description, due_date, priority, tags, completed):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tasks SET title=?, description=?, due_date=?, priority=?, tags=?, completed=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (title, description, due_date, priority, tags, int(bool(completed)), task_id))
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
    c.execute("SELECT id, title, description, due_date, priority, tags, completed FROM tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    conn.close()
    return row

def map_task_to_gc(task_id, event_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO gc_mapping (task_id, gc_event_id) VALUES (?, ?)", (task_id, event_id))
    conn.commit()
    conn.close()

def get_gc_event_id(task_id):
    conn = db_get_connection()
    c = conn.cursor()
    c.execute("SELECT gc_event_id FROM gc_mapping WHERE task_id=?", (task_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

# -----------------------
# Google Calendar helpers
# -----------------------
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_PICKLE = 'token.pickle'

def ensure_google_available():
    if not HAVE_GOOGLE:
        raise RuntimeError("Google client libraries not installed. Run:\n"
                           "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

def google_get_service():
    ensure_google_available()
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, 'rb') as f:
            creds = pickle.load(f)
    # If no valid creds, run the flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"{CREDENTIALS_FILE} not found. Create OAuth credentials and download JSON.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE, 'wb') as f:
            pickle.dump(creds, f)
    service = build('calendar', 'v3', credentials=creds)
    return service

def task_to_event_body(task):
    # task: (id, title, description, due_date, priority, tags, completed)
    tid, title, desc, due, priority, tags, completed = task
    # We'll make an all-day event on due date if provided; otherwise create event for today+priority offset
    if due:
        # Google all-day events use 'date' in 'start'/'end' and end is exclusive -> add 1 day
        try:
            dt = datetime.datetime.strptime(due, "%Y-%m-%d").date()
            end_dt = dt + datetime.timedelta(days=1)
            start = {'date': dt.isoformat()}
            end = {'date': end_dt.isoformat()}
        except Exception:
            # fallback: put event at 9am today
            start_dt = datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            end_dt = start_dt + datetime.timedelta(hours=1)
            start = {'dateTime': start_dt.isoformat()}
            end = {'dateTime': end_dt.isoformat()}
    else:
        start_dt = datetime.datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
        end_dt = start_dt + datetime.timedelta(hours=1)
        start = {'dateTime': start_dt.isoformat()}
        end = {'dateTime': end_dt.isoformat()}

    body = {
        'summary': f"[Task] {title}",
        'description': (desc or "") + ("\n\nTags: " + (tags or "")),
        'start': start,
        'end': end,
        # Put priority into description or use colorId if you like (colorId requires knowledge of calendars colors)
    }
    return body

def push_task_to_google(task):
    """
    Creates/updates the Google Calendar event for this local task.
    Returns event id.
    """
    service = google_get_service()
    event_body = task_to_event_body(task)
    existing_event_id = get_gc_event_id(task[0])
    calendar_id = 'primary'
    if existing_event_id:
        try:
            event = service.events().get(calendarId=calendar_id, eventId=existing_event_id).execute()
            # update the event
            updated = service.events().patch(calendarId=calendar_id, eventId=existing_event_id, body=event_body).execute()
            return updated['id']
        except Exception:
            # If it fails (deleted on calendar), create new
            created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            return created['id']
    else:
        created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return created['id']

class PlaceholderEntry(Entry):
    def __init__(self, master=None, placeholder="Placeholder", color="grey", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg = self["fg"]

        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._add_placeholder)

        self._add_placeholder()

    def _add_placeholder(self, event=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self["fg"] = self.placeholder_color

    def _clear_placeholder(self, event=None):
        if self["fg"] == self.placeholder_color:
            self.delete(0, END)
            self["fg"] = self.default_fg


# -----------------------
# Tkinter UI
# -----------------------
class TaskerApp:
    def __init__(self, root):
        self.root = root
        root.title("Minimal Tasker")
        root.geometry("900x600")

        # Top frame - quick add
        top = Frame(root, padx=8, pady=8)
        top.pack(fill=X)

        self.title_var = StringVar()
        self.title_entry = PlaceholderEntry(top, textvariable=self.title_var, width=40,
                                    placeholder="Task title")
        self.title_entry.pack(side=LEFT, padx=(0,8))

        self.tags_entry = PlaceholderEntry(top, width=20, placeholder="Tags")
        self.tags_entry.pack(side=LEFT, padx=(8,8))
        if HAVE_TKCAL:
            self.due_widget = DateEntry(top, width=12)
        else:
            self.due_var = StringVar()
            self.due_widget = Entry(top, textvariable=self.due_var, width=12)
            self.due_widget.insert(0, datetime.date.today().isoformat())
        self.due_widget.pack(side=LEFT, padx=(0,8))
        self.priority_var = IntVar(value=0)
        Spinbox(top, from_=0, to=5, width=3, textvariable=self.priority_var).pack(side=LEFT)
        Button(top, text="Add Task", command=self.quick_add).pack(side=LEFT)

        # Middle - filters and toolbar
        toolbar = Frame(root, padx=8, pady=4)
        toolbar.pack(fill=X)
        Label(toolbar, text="Filter tag:").pack(side=LEFT)
        self.filter_tag_var = StringVar()
        filter_entry = Entry(toolbar, textvariable=self.filter_tag_var, width=16)
        filter_entry.pack(side=LEFT, padx=(4,8))

        # Auto-apply filter as user types
        filter_entry.bind("<KeyRelease>", lambda e: self.load_tasks())

        # Sort dropdown with auto-apply
        self.sort_var = StringVar(value="due_date")
        sort_box = ttk.Combobox(toolbar, textvariable=self.sort_var,
                                values=["due_date", "priority", "title"], width=12)
        sort_box.pack(side=LEFT)
        sort_box.bind("<<ComboboxSelected>>", lambda e: self.load_tasks())
        Button(toolbar, text="Sync selected → Google Calendar", command=self.sync_selected_to_google).pack(side=RIGHT)

        # --- Default sort toggle ---
        self.default_sort_var = BooleanVar(value=True)
        Checkbutton(toolbar, text="Default sort", variable=self.default_sort_var,
                    command=self.load_tasks).pack(side=LEFT, padx=(8, 0))

        # Treeview for tasks
        columns = ("title","due","priority","tags","completed")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
        # Track current sort state
        self.sort_state = {}   # track sort directions

        def make_heading(col, label):
            self.tree.heading(col, text=label,
                            command=lambda c=col: self.sort_by_column(c))

        make_heading("title", "Title")
        make_heading("due", "Due Date")
        make_heading("priority", "Priority")
        make_heading("tags", "Tags")
        make_heading("completed", "Done")

        self.tree.column("title", width=380)
        self.tree.column("due", width=110)
        self.tree.column("priority", width=80, anchor=CENTER)
        self.tree.column("tags", width=160)
        self.tree.column("completed", width=60, anchor=CENTER)
        self.tree.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Bottom - action buttons
        bottom = Frame(root, padx=8, pady=8)
        bottom.pack(fill=X)
        Button(bottom, text="Edit Selected", command=self.edit_selected).pack(side=LEFT)
        Button(bottom, text="Delete Selected", command=self.delete_selected).pack(side=LEFT, padx=(8,0))
        Button(bottom, text="Mark Done/Undo", command=self.toggle_done).pack(side=LEFT, padx=(8,0))
        Button(bottom, text="Refresh", command=self.load_tasks).pack(side=RIGHT)

        # initial load
        self.load_tasks()

    def quick_add(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Empty title", "Please enter a task title.")
            return
        if HAVE_TKCAL:
            due = self.due_widget.get_date().isoformat()
        else:
            due = self.due_widget.get().strip() or None
        priority = self.priority_var.get()
        tags = self.tags_entry.get().strip()
        self.tags_entry.delete(0, END)
        tid = add_task(title, "", due, int(priority), tags)
        self.title_var.set("")
        self.load_tasks()
        # Optionally sync automatically? Not here — user triggers sync to Google
        messagebox.showinfo("Added", f"Task added (id={tid}). Use Sync to push to Google Calendar.")

    def load_tasks(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        tag = self.filter_tag_var.get().strip() or None

        if self.default_sort_var.get():
            # Our multi-level default sort: priority → due → title
            rows = get_tasks(filter_tag=tag, show_completed=True)
            rows.sort(
                key=lambda r: (
                    -int(r[4] or 0),                             # priority DESC
                    r[3] is None,                               # due_date NULLs last
                    r[3] or "9999-99-99",                       # due_date ASC
                    (r[1] or "").lower()                        # title ASC
                )
            )
        else:
            # Use manual UI-chosen sort
            sort_by = self.sort_var.get()
            rows = get_tasks(filter_tag=tag, sort_by=sort_by, show_completed=True)
        for r in rows:
            tid, title, desc, due, priority, tags, completed = r
            self.tree.insert("", "end", iid=str(tid),
                            values=(title, due or "", priority or 0, tags or "", "✓" if completed else ""))

    def clear_filter(self):
        self.filter_tag_var.set("")
        self.load_tasks()

    def get_selected_task_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a task.")
            return None
        return int(sel[0])

    def edit_selected(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        row = get_task(tid)
        if not row:
            messagebox.showerror("Error", "Task not found.")
            return
        # open edit dialog
        EditDialog(self.root, row, on_save=self.on_edit_save)

    def on_edit_save(self, task_data):
        # task_data: (id, title, description, due_date, priority, tags, completed)
        update_task(*task_data)
        self.load_tasks()

    def delete_selected(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        if messagebox.askyesno("Confirm", "Delete selected task?"):
            delete_task(tid)
            self.load_tasks()

    def toggle_done(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        row = get_task(tid)
        if not row:
            return
        completed = not bool(row[6])
        update_task(tid, row[1], row[2], row[3], row[4], row[5], int(completed))
        self.load_tasks()

    def on_double_click(self, event):
        # edit on double click
        self.edit_selected()

    def sync_selected_to_google(self):
        if not HAVE_GOOGLE:
            messagebox.showerror("Missing libs", "Google libraries not installed.\nRun:\n"
                                 "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            return
        tid = self.get_selected_task_id()
        if not tid:
            return
        task = get_task(tid)
        if not task:
            messagebox.showerror("Error", "Task not found.")
            return

        def worker():
            try:
                event_id = push_task_to_google(task)
                map_task_to_gc(tid, event_id)
                messagebox.showinfo("Synced", f"Task pushed to Google Calendar (event id: {event_id}).")
            except Exception as e:
                messagebox.showerror("Sync error", f"Error during Google sync:\n{e}")

        # run in separate thread so UI remains responsive
        threading.Thread(target=worker, daemon=True).start()
    
    def sort_by_column(self, col):
        # Toggle ASC/DESC
        direction = self.sort_state.get(col, False)
        self.sort_state[col] = not direction

        # Convert tree rows → Python list
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        
        # Convert values for correct sorting
        def convert(value):
            if col == "priority":
                try: return int(value)
                except: return 0
            if col == "due":
                try: return datetime.datetime.strptime(value, "%Y-%m-%d")
                except: return datetime.datetime.max
            return value.lower() if isinstance(value, str) else value

        rows.sort(key=lambda r: convert(r[0]), reverse=self.sort_state[col])

        # Rearrange rows
        for index, (val, iid) in enumerate(rows):
            self.tree.move(iid, "", index)

class EditDialog(simpledialog.Dialog):
    def __init__(self, parent, task_row, on_save):
        self.task_row = task_row
        self.on_save = on_save
        super().__init__(parent, title="Edit Task")

    def body(self, master):
        tid, title, desc, due, priority, tags, completed = self.task_row
        Label(master, text="Title:").grid(row=0, column=0, sticky=W)
        self.title_e = Entry(master, width=60)
        self.title_e.insert(0, title or "")
        self.title_e.grid(row=0, column=1, columnspan=3, sticky=W)

        Label(master, text="Due (YYYY-MM-DD):").grid(row=1, column=0, sticky=W)
        if HAVE_TKCAL:
            self.due_e = DateEntry(master)
            if due:
                try:
                    self.due_e.set_date(datetime.datetime.strptime(due, "%Y-%m-%d").date())
                except Exception:
                    pass
        else:
            self.due_e = Entry(master)
            if due:
                self.due_e.insert(0, due)
        self.due_e.grid(row=1, column=1, sticky=W)

        Label(master, text="Priority (0-5):").grid(row=1, column=2, sticky=W)
        self.priority_e = Spinbox(master, from_=0, to=5, width=4)
        self.priority_e.delete(0,END)
        self.priority_e.insert(0, str(priority or 0))
        self.priority_e.grid(row=1, column=3, sticky=W)

        Label(master, text="Tags (comma):").grid(row=2, column=0, sticky=W)
        self.tags_e = Entry(master, width=40)
        self.tags_e.insert(0, tags or "")
        self.tags_e.grid(row=2, column=1, sticky=W)

        Label(master, text="Completed:").grid(row=2, column=2, sticky=W)
        self.completed_var = IntVar(value=completed or 0)
        Checkbutton(master, variable=self.completed_var).grid(row=2, column=3, sticky=W)

        Label(master, text="Description:").grid(row=3, column=0, sticky=NW)
        self.desc_e = Text(master, width=60, height=8)
        self.desc_e.insert("1.0", desc or "")
        self.desc_e.grid(row=3, column=1, columnspan=3, sticky=W)

        return self.title_e

    def apply(self):
        tid, *_ = self.task_row
        title = self.title_e.get().strip()
        desc = self.desc_e.get("1.0", END).strip()
        due = self.due_e.get().strip() if not HAVE_TKCAL else self.due_e.get_date().isoformat()
        priority = int(self.priority_e.get())
        tags = self.tags_e.get().strip()
        completed = int(bool(self.completed_var.get()))
        new_row = (tid, title, desc, due, priority, tags, completed)
        # call back
        self.on_save(new_row)

# -----------------------
# Main
# -----------------------
def main():
    init_db()
    root = Tk()
    app = TaskerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
