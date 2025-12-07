import calendar
import datetime
import tkinter as tk
from tkinter import ttk

class PlaceholderEntry(ttk.Entry):
    def __init__(self, master=None, placeholder="Placeholder", color="grey", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = color

        self.default_style = self.cget("style") or ""

        style = ttk.Style()
        self.placeholder_style = f"{id(self)}.Placeholder.TEntry"
        style.configure(self.placeholder_style, foreground=self.placeholder_color)

        self.bind("<FocusIn>", self._clear)
        self.bind("<FocusOut>", self._restore)

        self._restore()

    def _is_placeholder(self):
        return self.get() == self.placeholder

    def _restore(self, event=None):
        if not self.get():
            self.configure(style=self.placeholder_style)
            self.delete(0, tk.END)
            self.insert(0, self.placeholder)

    def _clear(self, event=None):
        if self._is_placeholder():
            self.delete(0, tk.END)
            self.configure(style=self.default_style)

class CalendarPopup(tk.Toplevel):
    """
    A Toplevel popup showing a month grid. Callback receives a datetime.date.
    """

    def __init__(self, parent, selected_date=None, callback=None):
        super().__init__(parent)
        self.withdraw()
        self.transient(parent)
        self.title("")
        self.resizable(False, False)
        self.callback = callback
        self.parent = parent

        self.selected_date = selected_date or datetime.date.today()
        self.display_year = self.selected_date.year
        self.display_month = self.selected_date.month

        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.update_idletasks()

    def _build_ui(self):
        pad = 6
        frm = ttk.Frame(self, padding=pad)
        frm.grid(row=0, column=0)

        # --- Header with arrows and month name centered ---
        hdr = ttk.Frame(frm)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        hdr.columnconfigure(0, weight=1)
        hdr.columnconfigure(1, weight=0)
        hdr.columnconfigure(2, weight=0)
        hdr.columnconfigure(3, weight=0)
        hdr.columnconfigure(4, weight=1)

        self.prev_btn = ttk.Button(hdr, text="<", width=3, command=self._on_prev)
        self.prev_btn.grid(row=0, column=1, padx=5)

        self.header_label = ttk.Label(hdr, text="", anchor="center")
        self.header_label.grid(row=0, column=2, padx=5)

        self.next_btn = ttk.Button(hdr, text=">", width=3, command=self._on_next)
        self.next_btn.grid(row=0, column=3, padx=5)

        # --- Weekday labels aligned with day buttons ---
        self.wk_frame = ttk.Frame(frm)
        self.wk_frame.grid(row=1, column=0, sticky="nsew")
        for i, name in enumerate(calendar.day_abbr):
            lbl = ttk.Label(self.wk_frame, text=name[:2], anchor="center")
            lbl.grid(row=0, column=i, sticky="nsew", padx=1)
            self.wk_frame.columnconfigure(i, weight=1)

        # --- Days grid ---
        self.days_frame = ttk.Frame(frm)
        self.days_frame.grid(row=2, column=0, pady=(4, 0), sticky="nsew")
        for i in range(7):
            self.days_frame.columnconfigure(i, weight=1)

        # --- Footer ---
        footer = ttk.Frame(frm)
        footer.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(footer, text="Today", command=self._on_today).pack(side="left")
        ttk.Button(footer, text="Cancel", command=self._on_close).pack(side="right")

        self._draw_calendar()

    def _draw_calendar(self):
        # Clear previous widgets
        for w in self.days_frame.winfo_children():
            w.destroy()

        dt_name = datetime.date(self.display_year, self.display_month, 1).strftime("%B %Y")
        self.header_label.config(text=dt_name)

        month_cal = calendar.monthcalendar(self.display_year, self.display_month)

        for r, week in enumerate(month_cal):
            for c, day in enumerate(week):
                if day == 0:
                    lbl = ttk.Label(self.days_frame, text="", anchor="center")
                    lbl.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
                else:
                    btn = ttk.Button(self.days_frame, text=str(day))
                    dt = datetime.date(self.display_year, self.display_month, day)
                    if dt == self.selected_date:
                        btn.state(["selected"])
                    btn.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
                    btn.config(command=lambda d=dt: self._on_day_selected(d))

            # Ensure each row expands evenly
            self.days_frame.rowconfigure(r, weight=1)



    def _on_prev(self):
        y, m = self.display_year, self.display_month
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
        self.display_year, self.display_month = y, m
        self._draw_calendar()

    def _on_next(self):
        y, m = self.display_year, self.display_month
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
        self.display_year, self.display_month = y, m
        self._draw_calendar()

    def _on_today(self):
        self.selected_date = datetime.date.today()
        if self.callback:
            try:
                self.callback(self.selected_date)
            finally:
                self.destroy()

    def _on_day_selected(self, date_obj):
        self.selected_date = date_obj
        if self.callback:
            try:
                self.callback(date_obj)
            finally:
                self.destroy()

    def _on_close(self):
        self.destroy()

class DateEntry(ttk.Frame):
    """
    Composite widget with an entry (read-only) and a button that opens CalendarPopup.
    get_date() returns ISO string 'YYYY-MM-DD' or empty string.
    set_date(date_obj) accepts either datetime.date or ISO string.
    """
    def __init__(self, master=None, width=12, initial_date=None, **kwargs):
        super().__init__(master, **kwargs)
        self._value = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self._value, width=width, state="readonly")
        self.entry.pack(side="left", fill="x", expand=True)
        self.btn = ttk.Button(self, text="▾", width=2, command=self._open_popup)
        self.btn.pack(side="left", padx=(3,0))

        if initial_date:
            self.set_date(initial_date)
        else:
            self._value.set("")

        self._popup = None

    def _open_popup(self):
        sel = None
        try:
            if self._value.get():
                sel = datetime.datetime.strptime(self._value.get(), "%Y-%m-%d").date()
        except Exception:
            sel = datetime.date.today()

        self._popup = CalendarPopup(
            self.winfo_toplevel(),
            selected_date=sel,
            callback=self._on_date_chosen
        )

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()

        self._popup.geometry(f"+{x}+{y}")
        self._popup.deiconify()
        self._popup.focus_force()

    def _on_date_chosen(self, date_obj):
        if isinstance(date_obj, (datetime.date, datetime.datetime)):
            iso = date_obj.isoformat()
            self._value.set(iso)
        else:
            self._value.set(str(date_obj))

    def get_date(self):
        val = self._value.get()
        return val

    def set_date(self, date_obj_or_str):
        if isinstance(date_obj_or_str, str):
            self._value.set(date_obj_or_str)
        elif isinstance(date_obj_or_str, datetime.datetime):
            self._value.set(date_obj_or_str.date().isoformat())
        elif isinstance(date_obj_or_str, datetime.date):
            self._value.set(date_obj_or_str.isoformat())
        else:
            self._value.set("")
