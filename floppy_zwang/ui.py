import threading
import datetime
import logging
import tkinter as tk
from tkinter import ttk, messagebox

from db import add_task, update_task, delete_task, get_tasks, get_task, map_task_to_gc
from widgets import PlaceholderEntry, DateEntry
from dialogs import EditDialog
from google_sync import push_task_to_google

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class TaskerApp:
    def __init__(self, root, theme="litera"):
        self.root = root
        self.root.title("Simple Task Manager")
        self.root.geometry("900x600")

        # ttkbootstrap theme is set by the Window in main.py

        # --- Top frame ---
        top = ttk.Frame(root, padding=(8, 8))
        top.pack(fill=tk.X)

        # Use grid for even spacing
        top.columnconfigure(0, weight=2)   # title
        top.columnconfigure(1, weight=1)   # tags
        top.columnconfigure(2, weight=1)   # date
        top.columnconfigure(3, weight=0)   # priority spinbox
        top.columnconfigure(4, weight=0)   # add button

        self.title_entry = PlaceholderEntry(top, placeholder="Task title")
        self.title_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.tags_entry = PlaceholderEntry(top, placeholder="Tags")
        self.tags_entry.grid(row=0, column=1, sticky="ew", padx=8)

        self.due_widget = DateEntry(top)
        self.due_widget.grid(row=0, column=2, sticky="ew", padx=8)

        self.priority_var = tk.IntVar(value=2)
        self.priority_spin = ttk.Spinbox(
            top, from_=0, to=5, width=3, textvariable=self.priority_var
        )
        self.priority_spin.grid(row=0, column=3, sticky="ew", padx=8)

        ttk.Button(top, text="Add Task", command=self.quick_add).grid(
            row=0, column=4, sticky="ew"
        )


        # --- Toolbar ---
        toolbar = ttk.Frame(root, padding=(8,4))
        toolbar.pack(fill=tk.X)
        ttk.Label(toolbar, text="Filter tag:").pack(side=tk.LEFT)
        self.filter_tag_var = tk.StringVar()
        filter_entry = ttk.Entry(toolbar, textvariable=self.filter_tag_var, width=16)
        filter_entry.pack(side=tk.LEFT, padx=(4, 8))
        filter_entry.bind("<KeyRelease>", lambda e: self.load_tasks())

        self.sort_var = tk.StringVar(value="due_date")
        sort_box = ttk.Combobox(
            toolbar, textvariable=self.sort_var,
            values=["due_date", "priority", "title"], width=12
        )
        sort_box.pack(side=tk.LEFT)
        sort_box.bind("<<ComboboxSelected>>", lambda e: self.load_tasks())

        ttk.Button(toolbar, text="Sync selected to Google Calendar",
                  command=self.sync_selected_to_google).pack(side=tk.RIGHT)

        self.default_sort_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Default sort",
                        variable=self.default_sort_var, command=self.load_tasks).pack(side=tk.LEFT, padx=(8, 0))

        # --- Treeview ---
        columns = ("title", "due", "priority", "tags", "completed")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
        self.sort_state = {}

        def make_heading(col, label):
            self.tree.heading(col, text=label, command=lambda c=col: self.sort_by_column(c))

        make_heading("title", "Title")
        make_heading("due", "Due Date")
        make_heading("priority", "Priority")
        make_heading("tags", "Tags")
        make_heading("completed", "Done")

        self.tree.column("title", width=380)
        self.tree.column("due", width=110)
        self.tree.column("priority", width=80, anchor="center")
        self.tree.column("tags", width=160)
        self.tree.column("completed", width=60, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self.on_double_click)

        # --- Bottom buttons ---
        bottom = ttk.Frame(root, padding=(8,8))
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="Edit Selected", command=self.edit_selected).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Delete Selected", command=self.delete_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(bottom, text="Mark Done/Undo", command=self.toggle_done).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(bottom, text="Refresh", command=self.load_tasks).pack(side=tk.RIGHT)

        self.load_tasks()

    # --- Methods ---
    def quick_add(self):
        title = self._get_clean_text(self.title_entry)
        tags = self._get_clean_text(self.tags_entry)
        due = getattr(self.due_widget, "get_date", lambda: self.due_widget.get_date())()
        priority = self.priority_var.get()

        # ----- VALIDATION RULES -----

        # Require title
        if not title:
            messagebox.showwarning("Missing title", "Please enter a task title.")
            return

        # Require due date
        if not due:
            messagebox.showwarning("Missing date", "Please pick a due date.")
            return

        # Require priority
        if priority is None:
            messagebox.showwarning("Missing priority", "Please set a priority.")
            return

        # ----- SAVE TASK -----
        tid = add_task(title, "", due, priority, tags)

        # Clear inputs
        self.title_entry.delete(0, tk.END)
        self.tags_entry.delete(0, tk.END)

        self.title_entry.delete(0, tk.END)
        self.title_entry._restore()  # restore placeholder

        self.tags_entry.delete(0, tk.END)
        self.tags_entry._restore()  # restore placeholder

        # Reset priority spinbox
        self.priority_var.set(0)

        # Reset date entry
        self.due_widget.set_date("")  # clear date

        # Reload list
        self.root.after(0, self.load_tasks)
        logger.info(f"Added task {tid}: {title}")

    def load_tasks(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        tag = self.filter_tag_var.get().strip() or None
        if self.default_sort_var.get():
            rows = get_tasks(filter_tag=tag, show_completed=True)
            rows.sort(key=lambda r: (-int(r[4] or 0), r[3] is None, r[3] or "9999-99-99", (r[1] or "").lower()))
        else:
            rows = get_tasks(filter_tag=tag, sort_by=self.sort_var.get(), show_completed=True)
        for r in rows:
            tid, title, desc, due, priority, tags, completed = r
            self.tree.insert("", "end", iid=str(tid),
                             values=(title, due or "", priority or 0, tags or "", "✓" if completed else ""))

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
        # Non-blocking modal dialog (grab_set will prevent interaction with parent)
        EditDialog(self.root, row, on_save=self.on_edit_save)

    def on_edit_save(self, task_data):
        update_task(*task_data)
        logger.info(f"Updated task {task_data[0]}")
        self.root.after(0, self.load_tasks)

    def delete_selected(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        if messagebox.askyesno("Confirm", "Delete selected task?"):
            delete_task(tid)
            logger.info(f"Deleted task {tid}")
            self.root.after(0, self.load_tasks)

    def toggle_done(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        row = get_task(tid)
        if not row:
            return
        completed = not bool(row[6])
        update_task(tid, row[1], row[2], row[3], row[4], row[5], int(completed))
        self.root.after(0, self.load_tasks)

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.edit_selected()

    def sync_selected_to_google(self):
        tid = self.get_selected_task_id()
        if not tid:
            return
        task = get_task(tid)
        if not task:
            return

        def worker():
            try:
                event_id = push_task_to_google(task)
                map_task_to_gc(tid, event_id)
                self.root.after(0, lambda: messagebox.showinfo(
                    "Synced", f"Task pushed to Google Calendar (event id: {event_id})."))
                logger.info(f"Synced task {tid} to Google Calendar")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Sync error", f"Error during Google sync:\n{e}"))
                logger.error(f"Google sync error for task {tid}: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def sort_by_column(self, col):
        direction = self.sort_state.get(col, False)
        self.sort_state[col] = not direction
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        def convert(value):
            if col == "priority":
                try:
                    return int(value)
                except Exception:
                    return 0
            if col == "due":
                try:
                    return datetime.datetime.strptime(value, "%Y-%m-%d")
                except Exception:
                    return datetime.datetime.max
            return value.lower() if isinstance(value, str) else value
        rows.sort(key=lambda r: convert(r[0]), reverse=self.sort_state[col])
        for index, (val, iid) in enumerate(rows):
            self.tree.move(iid, "", index)

    def _is_placeholder(self, entry_widget):
        if isinstance(entry_widget, PlaceholderEntry):
            return entry_widget._is_placeholder()
        return False

    def _get_clean_text(self, entry_widget):
        if isinstance(entry_widget, PlaceholderEntry):
            if entry_widget._is_placeholder():
                return ""
        return entry_widget.get().strip()