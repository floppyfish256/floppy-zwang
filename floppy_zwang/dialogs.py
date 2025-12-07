import datetime
import tkinter as tk
from tkinter import ttk

from widgets import DateEntry
from widgets import PlaceholderEntry

class EditDialog:
    def __init__(self, parent, task_row, on_save):
        self.parent = parent
        self.task_row = task_row
        self.on_save = on_save

        self.window = tk.Toplevel(parent)
        self.window.title("Edit Task")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

        self.build_ui()

        self.window.update_idletasks()
        self.window.deiconify()
        self.window.focus_force()

    def build_ui(self):
        tid, title, desc, due, priority, tags, completed = self.task_row

        frm = ttk.Frame(self.window, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w")
        self.title_e = ttk.Entry(frm, width=60)
        self.title_e.insert(0, title or "")
        self.title_e.grid(row=0, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        ttk.Label(frm, text="Due date:").grid(row=1, column=0, sticky="w")
        self.due_e = DateEntry(frm)
        if due:
            try:
                self.due_e.set_date(datetime.datetime.strptime(due, "%Y-%m-%d").date())
            except Exception:
                self.due_e.set_date(due)
        self.due_e.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frm, text="Priority:").grid(row=1, column=2, sticky="w")
        self.priority_e = ttk.Spinbox(frm, from_=0, to=5, width=4)
        self.priority_e.delete(0, "end")
        self.priority_e.insert(0, str(priority or 0))
        self.priority_e.grid(row=1, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(frm, text="Tags:").grid(row=2, column=0, sticky="w")
        self.tags_e = ttk.Entry(frm, width=40)
        self.tags_e.insert(0, tags or "")
        self.tags_e.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frm, text="Completed:").grid(row=2, column=2, sticky="w")
        self.completed_var = tk.IntVar(value=1 if completed else 0)
        ttk.Checkbutton(frm, variable=self.completed_var).grid(row=2, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(frm, text="Description:").grid(row=3, column=0, sticky="nw", pady=(6,0))
        self.desc_e = tk.Text(frm, width=60, height=8)
        self.desc_e.insert("1.0", desc or "")
        self.desc_e.grid(row=3, column=1, columnspan=3, sticky="we", padx=4, pady=2)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=1, columnspan=3, sticky="e", pady=(8, 0))

        ttk.Button(btn_frame, text="Save", command=self.ok).pack(side="right", padx=(4,0))
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side="right")

        frm.columnconfigure(1, weight=1)

    def ok(self):
        tid, *_ = self.task_row
        due_val = ""
        try:
            due_val = self.due_e.get_date()
        except Exception:
            try:
                due_val = self.due_e.entry.get()
            except Exception:
                due_val = ""
        data = (
            tid,
            self.title_e.get().strip(),
            self.desc_e.get("1.0", "end").strip(),
            due_val or "",
            int(self.priority_e.get()),
            self.tags_e.get().strip(),
            int(bool(self.completed_var.get())),
        )
        try:
            self.on_save(data)
        finally:
            self.window.destroy()

    def cancel(self):
        self.window.destroy()
