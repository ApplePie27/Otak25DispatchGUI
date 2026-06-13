"""
GUI.PY
The Tkinter desktop interface for HQ Dispatchers.
Implements non-blocking ThreadPoolExecutors, SLA Timer evaluations, 
and HTTP IPC requests to notify the Discord Bot of changes.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from data_manager import DataManager
from datetime import datetime
import os
import sys
import logging
import configparser
import csv
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# Audio Support for High-Priority Alarms
try:
    import winsound
    AUDIO_ENABLED = True
except ImportError:
    AUDIO_ENABLED = False

# Modern UI Theme
try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

class ToolTip:
    """Helper class to display floating text when hovering over buttons."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip: return
        x, y = event.x_root + 20, event.y_root + 10
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{int(x)}+{int(y)}")
        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", foreground="black", relief="solid", 
                         borderwidth=1, font=("tahoma", "8", "normal"), wraplength=300, justify='left')
        label.pack(ipadx=2, ipady=2)

    def hide_tooltip(self, event):
        if self.tooltip: self.tooltip.destroy()
        self.tooltip = None

class ScrolledTextHandler(logging.Handler):
    """Routes standard Python logging directly into the Tkinter UI window."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    def emit(self, record):
        msg = self.format(record)
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.configure(state="disabled")
        self.text_widget.see(tk.END)

class DispatchCallApp:
    def __init__(self, root, logger, data_manager):
        self.root = root
        self.logger = logger
        self.manager = data_manager
        
        # Using a single-worker executor prevents the UI from freezing during network writes
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        self.known_calls = set()
        self.is_first_load = True
        self.last_update_count = -1
        self.last_redraw_time = datetime.now()
        
        # Triggers Audio Sirens and SLA Overrides
        self.high_priority_codes = ["White / Mayday", "Silver", "Black", "Red", "Blue", "Adam"]
        
        self.root.title("HQ Dispatch Center V5.3")
        self.root.resizable(True, True)
        
        if HAS_SV_TTK:
            sv_ttk.set_theme("light") # Default theme
            
        self.config = configparser.ConfigParser()
        self.config.optionxform = str # Prevents Python from forcing lowercase on keys
        self.load_config()
        
        self.current_user = None
        self.current_user_role = None
        self.is_dirty = False
        self.is_loading_data = False
        
        if not self.ensure_user_logged_in():
            self.root.destroy()
            return
            
        self._build_main_ui()
        self.apply_theme_colors() 
        self.root.deiconify()

    # ==========================================
    # HARDWARE & THEME CONTROLS
    # ==========================================
    def _play_siren(self):
        if AUDIO_ENABLED:
            for _ in range(8): # Rapid submarine klaxon
                winsound.Beep(1500, 150) 
                winsound.Beep(1000, 150)

    def _play_ping(self):
        if AUDIO_ENABLED: winsound.Beep(600, 400)

    def _sanitize_for_tkinter(self, text):
        """Prevents emojis from mobile phones from crashing the Tkinter engine."""
        if not text: return ""
        return ''.join(c for c in str(text) if ord(c) <= 0xFFFF)
        
    def toggle_theme(self):
        if HAS_SV_TTK:
            if sv_ttk.get_theme() == "dark": sv_ttk.set_theme("light")
            else: sv_ttk.set_theme("dark")
            self.apply_theme_colors()

    def apply_theme_colors(self):
        """Dynamically switches SLA highlight tags based on Light/Dark mode."""
        is_dark = False
        if HAS_SV_TTK:
            is_dark = sv_ttk.get_theme() == "dark"
        
        # Text Entry fields
        bg_color = "#1e1e1e" if is_dark else "#ffffff"
        fg_color = "white" if is_dark else "black"
        self.description_entry.configure(bg=bg_color, fg=fg_color, insertbackground=fg_color)
        
        # Vivid Row Selection Override
        style = ttk.Style()
        style.map("Treeview", background=[('selected', '#0078D7')], foreground=[('selected', 'white')])
        
        # Table Row Tags
        self.table.tag_configure("hascode", background="#222222" if is_dark else "#e8e8e8", foreground="white" if is_dark else "black")
        self.table.tag_configure("nocode", background="#222222" if is_dark else "#f0f0f0", foreground="white" if is_dark else "black")
        self.table.tag_configure("resolved", background="#1e4d2b" if is_dark else "#d0f0c0", foreground="white" if is_dark else "black")
        self.table.tag_configure("cancelled", background="#4d4d4d" if is_dark else "#cccccc", foreground="#999999" if is_dark else "#666666")
        self.table.tag_configure("high_priority", background="#3a5f80" if is_dark else "#cce5ff", foreground="white" if is_dark else "black")
        self.table.tag_configure("sla_critical", background="#8B0000", foreground="white") 

    # ==========================================
    # UI CONSTRUCTION
    # ==========================================
    def _build_main_ui(self):
        self.sort_column = "ReportID"
        self.sort_direction = "ASC"
        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.cancelled_status_var = tk.BooleanVar(value=False)
        self.resolution_status_var = tk.BooleanVar(value=False)
        self.resolved_by_var = tk.StringVar()
        self.code_description_var = tk.StringVar()
        
        self.create_status_bar()
        self.create_log_area()
        self.setup_logging_handler()
        self.status_var.set(f"User: {self.current_user} ({self.current_user_role})")
        
        self.create_table()
        self.create_menu_bar()
        self.create_input_fields()
        self.create_buttons()
        self.create_search_bar()
        self.configure_grid_weights()
        self._apply_permissions()
        self._setup_keyboard_shortcuts()
        self._setup_dirty_tracking()
        
        self.update_table()
        self.start_auto_refresh()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Button-1>", self._on_click_outside)

    def load_config(self):
        self.config.read('config.ini')
        self.auto_refresh_interval_ms = self.config.getint('APPLICATION', 'auto_refresh_seconds', fallback=10) * 1000
        self.auto_scroll_var = tk.BooleanVar(value=self.config.getboolean('APPLICATION', 'auto_scroll_to_latest', fallback=True))
        
        self.desc_to_code_map = {}
        if self.config.has_section('CODES'):
            for desc, value in self.config.items('CODES'):
                self.desc_to_code_map[desc.strip()] = value.split('|')[0].strip()
        else:
            self.desc_to_code_map = {"General Situations": "No_Code"}

        self.source_options = {}
        if self.config.has_section('SOURCES'):
            for medium, sources in self.config.items('SOURCES'):
                self.source_options[medium.capitalize()] = [s.strip() for s in sources.split(',')]

    def setup_logging_handler(self):
        gui_handler = ScrolledTextHandler(self.log_area)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(gui_handler)

    def ensure_user_logged_in(self):
        users = dict(self.config.items('USERS')) if self.config.has_section('USERS') else {}
        if not users:
            messagebox.showerror("Error", "[USERS] missing in config.ini")
            return False
        while not self.current_user:
            username = simpledialog.askstring("Login", "Enter your username:", parent=self.root)
            if username is None: return False
            user = username.strip().lower()
            if user in users:
                self.current_user = user
                self.current_user_role = users[user]
                return True
            else:
                messagebox.showwarning("Failed", "Invalid username.")
        return True

    def _apply_permissions(self):
        """Admins can view and export liability audit logs. Users cannot."""
        if self.current_user_role == 'admin': 
            self.history_button.grid()
            self.file_menu.entryconfig("Export Complete Audit Log", state="normal")
        else: 
            self.history_button.grid_remove()
            self.file_menu.entryconfig("Export Complete Audit Log", state="disabled")
        
    def _setup_keyboard_shortcuts(self):
        self.root.bind('<Control-s>', lambda event: self.modify_call() if self.table.selection() else None)
        self.root.bind('<Control-n>', lambda event: self.clear_input_fields())

    def _set_dirty_flag(self, *args):
        if self.is_loading_data: return
        self.is_dirty = True

    def _setup_dirty_tracking(self):
        """Tracks if user has unsaved text, protecting them from auto-refresh deletion."""
        self.caller_var.trace_add("write", self._set_dirty_flag)
        self.location_var.trace_add("write", self._set_dirty_flag)
        self.code_var.trace_add("write", self._set_dirty_flag)
        self.cancelled_status_var.trace_add("write", self._set_dirty_flag)
        self.resolved_by_var.trace_add("write", self._set_dirty_flag)
        self.resolution_status_var.trace_add("write", self._set_dirty_flag)
        self.description_entry.bind("<KeyRelease>", self._set_dirty_flag)
        self.caller_var.trace_add("write", lambda *args: self.caller_var.set(self.caller_var.get().upper()))

    def create_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status_bar.grid(row=5, column=0, columnspan=2, sticky="ew")

    def create_log_area(self):
        self.log_area = scrolledtext.ScrolledText(self.root, height=5, state="disabled")
        self.log_area.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

    def create_menu_bar(self):
        menubar = tk.Menu(self.root)
        self.file_menu = tk.Menu(menubar, tearoff=0)
        
        if HAS_SV_TTK:
            self.file_menu.add_command(label="Toggle Light/Dark Mode 🌓", command=self.toggle_theme)
            self.file_menu.add_separator()
            
        self.file_menu.add_command(label="Change User", command=self.change_user)
        self.file_menu.add_command(label="Export Report to CSV", command=self.export_report)
        self.file_menu.add_command(label="Export Complete Audit Log", command=self.export_audit_log)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=self.file_menu)
        self.root.config(menu=menubar)

    def create_input_fields(self):
        fields_frame = ttk.LabelFrame(self.root, text="Dispatch Call Details")
        fields_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        uniform_width = 30
        
        ttk.Label(fields_frame, text="Input Medium:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        input_medium_cb = ttk.Combobox(fields_frame, textvariable=self.input_medium_var, state="readonly", values=list(self.source_options.keys()), width=uniform_width)
        input_medium_cb.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        input_medium_cb.bind("<<ComboboxSelected>>", self.update_source_options)
        
        ttk.Label(fields_frame, text="Source:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.source_cb = ttk.Combobox(fields_frame, textvariable=self.source_var, state="readonly", width=uniform_width)
        self.source_cb.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        self.update_source_options()
        
        ttk.Label(fields_frame, text="Caller ID:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(fields_frame, textvariable=self.caller_var, width=uniform_width+3).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(fields_frame, text="Location:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(fields_frame, textvariable=self.location_var, width=uniform_width+3).grid(row=2, column=1, padx=5, pady=2, sticky="w")
        
        all_descriptions = list(self.desc_to_code_map.keys())
        ttk.Label(fields_frame, text="Situation:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        code_cb = ttk.Combobox(fields_frame, textvariable=self.code_var, state="readonly", values=all_descriptions, width=uniform_width)
        code_cb.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        code_cb.bind("<<ComboboxSelected>>", self.update_code_description)
        
        if all_descriptions: self.code_var.set(all_descriptions[0])

        ttk.Label(fields_frame, text="Assigned Code:").grid(row=3, column=2, padx=5, pady=2, sticky="w")
        ttk.Label(fields_frame, textvariable=self.code_description_var, font=("TkDefaultFont", 9, "bold")).grid(row=3, column=3, columnspan=2, padx=5, pady=2, sticky="w")
        
        ttk.Label(fields_frame, text="Description:").grid(row=4, column=0, padx=5, pady=2, sticky="nw")
        
        desc_frame = ttk.Frame(fields_frame)
        desc_frame.grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky="w")
        
        if HAS_SV_TTK:
            self.description_entry = scrolledtext.ScrolledText(desc_frame, height=5, width=60, borderwidth=1, relief="solid", bg="#1e1e1e", fg="white", insertbackground="white")
        else:
            self.description_entry = scrolledtext.ScrolledText(desc_frame, height=5, width=60, borderwidth=1, relief="solid")
        self.description_entry.pack(side="left")
        
        ttk.Checkbutton(fields_frame, text="Resolved", variable=self.resolution_status_var, command=self.toggle_resolved_entry).grid(row=5, column=0, padx=5, pady=5, sticky="w")
        resolved_frame = ttk.Frame(fields_frame)
        resolved_frame.grid(row=5, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(resolved_frame, text="Resolved By:  ").pack(side="left", padx=(0, 4))
        self.resolved_by_entry = ttk.Entry(resolved_frame, textvariable=self.resolved_by_var, state="disabled", width=uniform_width)
        self.resolved_by_entry.pack(side="left")
        
        ttk.Checkbutton(fields_frame, text="Cancelled / Void", variable=self.cancelled_status_var).grid(row=6, column=0, padx=5, pady=5, sticky="w")

        self.update_code_description()

    def update_code_description(self, event=None):
        self.code_description_var.set(self.desc_to_code_map.get(self.code_var.get(), "N/A"))

    def update_source_options(self, event=None):
        options = self.source_options.get(self.input_medium_var.get(), [])
        self.source_cb['values'] = options
        self.source_var.set(options[0] if options else "")

    def create_buttons(self):
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        style = ttk.Style()
        style.configure("Bold.TButton", font=("TkDefaultFont", 10, "bold"))
        
        self.primary_action_button = ttk.Button(buttons_frame, text="ADD CALL", command=self.add_call, style="Bold.TButton")
        self.primary_action_button.grid(row=0, column=0, padx=5, pady=5)
        self.clear_button = ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_input_fields)
        self.clear_button.grid(row=0, column=1, padx=5, pady=5)
        self.history_button = ttk.Button(buttons_frame, text="View History", command=self.view_call_history)
        self.history_button.grid(row=0, column=2, padx=5, pady=5)
        self.passdown_button = ttk.Button(buttons_frame, text="📋 Shift Passdown Notes", command=self.open_passdown_notes)
        self.passdown_button.grid(row=0, column=3, padx=(30, 5), pady=5)

        self.action_buttons = [self.primary_action_button, self.clear_button, self.history_button, self.passdown_button]

    def _on_manual_scroll(self, event=None):
        self.auto_scroll_var.set(False)

    def create_table(self):
        self.columns = {
            "ReportID": ("Call ID", 80), "CallDate": ("Date", 80), "CallTime": ("Time", 60), "TimeOpen": ("Time Open", 80),
            "ResolutionStatus": ("Resolved?", 70), "ResolutionTimestamp": ("Resolved At", 120), "ResolvedBy": ("Resolved By", 100),
            "Cancelled": ("Cancelled?", 70),
            "InputMedium": ("Medium", 100), "Source": ("Source", 100), "Caller": ("Caller", 100),
            "Location": ("Location", 120), "Code": ("Code", 150), "Description": ("Description", 300),
            "CreatedBy": ("Created By", 100)
        }
        
        table_frame = ttk.Frame(self.root)
        table_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.table = ttk.Treeview(table_frame, columns=list(self.columns.keys()), show="headings")
        for col, (heading, width) in self.columns.items():
            self.table.heading(col, text=heading, command=lambda _col=col: self.sort_table(_col))
            self.table.column(col, width=width, anchor="w" if col == "Description" else "center")
        
        self.scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=self.scrollbar.set)
        
        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)
        self.table.bind("<MouseWheel>", self._on_manual_scroll)
        self.scrollbar.bind("<ButtonPress-1>", self._on_manual_scroll)
        self.scrollbar.bind("<B1-Motion>", self._on_manual_scroll)
        
        self.table.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

    def sort_table(self, col):
        if col == "TimeOpen": col = "CallTime"
        if self.sort_column == col: self.sort_direction = "DESC" if self.sort_direction == "ASC" else "ASC"
        else: self.sort_column, self.sort_direction = col, "ASC"
        self.update_table(update_behavior='preserve')

    def create_search_bar(self):
        search_frame = ttk.Frame(self.root)
        search_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.grid(row=0, column=1, padx=5, sticky="w")
        search_entry.bind("<KeyRelease>", lambda e: self.on_search())
        
        scroll_check = ttk.Checkbutton(search_frame, text="Auto-Scroll to Latest", variable=self.auto_scroll_var)
        scroll_check.grid(row=0, column=2, padx=(20, 5), sticky="w")

    def configure_grid_weights(self):
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def toggle_resolved_entry(self):
        state = "normal" if self.resolution_status_var.get() else "disabled"
        self.resolved_by_entry.configure(state=state)
        if state == "disabled": self.resolved_by_var.set("")

    def _set_ui_busy(self, is_busy):
        """Disables buttons while background threads are saving to database."""
        state = "disabled" if is_busy else "normal"
        for button in self.action_buttons: button.config(state=state)
        if is_busy: self.status_var.set("Working...")
        else:
            self.status_var.set("Ready")
            self._apply_permissions()

    def _validate_fields(self):
        if not self.caller_var.get().strip(): return False
        if not self.location_var.get().strip(): return False
        if not self.description_entry.get("1.0", tk.END).strip(): return False
        if self.resolution_status_var.get() and not self.resolved_by_var.get().strip(): return False
        return True

    def _run_in_thread(self, target, callback, *args):
        """Wrapper to prevent the Tkinter GUI from freezing during network drive writes."""
        self._set_ui_busy(True)
        def worker():
            try:
                result = target(*args)
                if self.root.winfo_exists(): self.root.after(0, callback, True, result)
            except Exception as e:
                if self.root.winfo_exists(): self.root.after(0, callback, False, str(e))
            finally:
                if self.root.winfo_exists(): self.root.after(0, self._set_ui_busy, False)
        self.executor.submit(worker)

    def _signal_discord_bot(self, endpoint, report_id, source=""):
        """Sends a lightweight HTTP POST to the Discord Bot to wake it up."""
        payload = {"report_id": report_id, "source": source}
        try:
            req = urllib.request.Request(f"http://localhost:8080/{endpoint}", data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=1.5): pass
        except Exception as e:
            self.logger.warning(f"Background Discord signaling failed: {e}")

    # ==========================================
    # LOGIC CONTROLLERS
    # ==========================================
    def add_call(self):
        if not self._validate_fields(): return
        self.primary_action_button.config(state="disabled")

        call_data = {
            "InputMedium": self.input_medium_var.get(), "Source": self.source_var.get(),
            "Caller": self.caller_var.get().strip(), "Location": self.location_var.get().strip(),
            "Code": self.desc_to_code_map.get(self.code_var.get(), ""), "Description": self.description_entry.get("1.0", tk.END).strip(),
            "ResolutionStatus": self.resolution_status_var.get(), "ResolvedBy": self.resolved_by_var.get().strip(),
            "Cancelled": self.cancelled_status_var.get()
        }
        self._run_in_thread(self.manager.add_call, self._on_add_call_complete, call_data, self.current_user)

    def _on_add_call_complete(self, success, new_report_id):
        if success:
            self.logger.info(f"Call added: {new_report_id}")
            self.is_dirty = False
            
            if self.input_medium_var.get().strip() != "Social Media":
                self.executor.submit(self._signal_discord_bot, "dispatch", new_report_id, self.source_var.get().strip())
            
            self.known_calls.add(new_report_id)
            self.last_update_count = self.manager.check_if_updated()
            self.update_table(update_behavior='focus', target_id=new_report_id, was_added=True)
        else:
            messagebox.showerror("Database Error", f"Failed to add call: {new_report_id}")
            self.primary_action_button.config(state="normal")

    def modify_call(self):
        if not self.table.selection(): return
        if not self._validate_fields(): return
        
        self.primary_action_button.config(state="disabled")

        report_id = self.table.item(self.table.selection()[0])["values"][0]
        
        updated_call = {
            "InputMedium": self.input_medium_var.get(), "Source": self.source_var.get(),
            "Caller": self.caller_var.get().strip(), "Location": self.location_var.get().strip(),
            "Code": self.desc_to_code_map.get(self.code_var.get(), ""), "Description": self.description_entry.get("1.0", tk.END).strip(),
            "ResolutionStatus": self.resolution_status_var.get(), "ResolvedBy": self.resolved_by_var.get().strip(),
            "Cancelled": self.cancelled_status_var.get()
        }
        
        callback = lambda success, res: self._on_modify_call_complete(success, res, report_id)
        self._run_in_thread(self.manager.modify_call, callback, report_id, updated_call, self.current_user)

    def _on_modify_call_complete(self, success, result_or_error, report_id):
        if success:
            self.is_dirty = False
            self.last_update_count = self.manager.check_if_updated()
            self.update_table(clear_fields=True)
            self.executor.submit(self._signal_discord_bot, "update", report_id)
        else:
            messagebox.showerror("Database Error", f"Failed to modify call: {result_or_error}")
            self.primary_action_button.config(state="normal")

    def load_selected_call(self, event):
        if self.is_dirty and not messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?"): return "break"
        if not self.table.selection(): return
        
        self.primary_action_button.config(text="SAVE MODIFICATION", command=self.modify_call, style="Bold.TButton")
        item = self.table.item(self.table.selection()[0])
        call = dict(zip(self.columns.keys(), item['values']))
        report_id = call.get("ReportID")
        
        self.is_loading_data = True
        self._run_in_thread(self.manager.get_call_by_id, self._on_load_selected_fetched, report_id)

    def _on_load_selected_fetched(self, success, full_call):
        try:
            if not success or not full_call: return
            
            call = dict(full_call)
            self.input_medium_var.set(call.get("InputMedium", ""))
            self.update_source_options()
            self.source_var.set(call.get("Source", ""))
            self.caller_var.set(self._sanitize_for_tkinter(call.get("Caller", "")))
            self.location_var.set(self._sanitize_for_tkinter(call.get("Location", "")))
            
            db_code = call.get("Code", "")
            sit_desc = next((k for k, v in self.desc_to_code_map.items() if v == db_code), None)
            if not sit_desc: sit_desc = next((d for d in self.desc_to_code_map.keys() if d.lower() == "general situations"), list(self.desc_to_code_map.keys())[0])
            self.code_var.set(sit_desc)
            self.update_code_description()
            
            self.description_entry.delete("1.0", tk.END)
            self.description_entry.insert(tk.END, self._sanitize_for_tkinter(call.get("Description", "")))

            self.cancelled_status_var.set(str(call.get("Cancelled", "False")).lower() in ('true', '1'))
            self.resolution_status_var.set(str(call.get("ResolutionStatus", "False")).lower() in ('true', '1'))
            self.toggle_resolved_entry()
            self.resolved_by_var.set(self._sanitize_for_tkinter(call.get("ResolvedBy", "")))

        finally: 
            self.is_loading_data = False
            self.is_dirty = False

    def clear_input_fields(self):
        if self.is_dirty and not messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?"): return
        self.is_loading_data = True
        try:
            if self.table.selection(): self.table.selection_remove(self.table.selection())
            self.caller_var.set("")
            self.location_var.set("")
            self.description_entry.delete("1.0", tk.END)
            self.cancelled_status_var.set(False)
            self.resolution_status_var.set(False)
            self.resolved_by_var.set("")
            self.toggle_resolved_entry()

            all_desc = list(self.desc_to_code_map.keys())
            if "general situations" in [d.lower() for d in all_desc]: self.code_var.set(next(d for d in all_desc if d.lower() == "general situations"))
            elif all_desc: self.code_var.set(all_desc[0])

            self.update_code_description()
            self.primary_action_button.config(text="ADD CALL", command=self.add_call, style="Bold.TButton")
        finally: self.is_loading_data = False
        self.is_dirty = False

    def _on_click_outside(self, event):
        try:
            if event.widget.winfo_class() in ('Frame', 'Label', 'Tk', 'TFrame', 'TLabel', 'LabelFrame', 'TLabelFrame'):
                self.clear_input_fields()
        except AttributeError: pass

    # ==========================================
    # DATA EXPORTS & UPDATES
    # ==========================================
    def export_report(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Export Dispatch Calls")
        if not filename: return
        self._run_in_thread(self.manager.get_all_calls, lambda s, r: self._on_export_data_fetched(s, r, filename), self.sort_column, self.sort_direction)

    def export_audit_log(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Export Audit Log")
        if not filename: return
        self._run_in_thread(self.manager.get_full_audit_log, lambda s, r: self._on_export_data_fetched(s, r, filename))

    def _on_export_data_fetched(self, success, rows, filename):
        if not success or not rows: return
        try:
            with open(filename, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows: writer.writerow(dict(row))
            messagebox.showinfo("Export Successful", f"Data successfully exported to\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to write CSV file: {e}")
            
    def change_user(self):
        if self.is_dirty and not messagebox.askyesno("Unsaved Changes", "Continue and lose changes?"): return
        original_user = self.current_user
        self.current_user = None 
        if self.ensure_user_logged_in():
            if self.current_user != original_user:
                self.status_var.set(f"User changed to: {self.current_user} ({self.current_user_role})")
                self._apply_permissions()
                self.clear_input_fields()
        else: self.current_user = original_user

    def update_table(self, update_behavior='preserve', target_id=None, was_added=False, clear_fields=False):
        """Fetches fresh data and calculates dynamic SLA colors."""
        pre_selection_id = self.table.item(self.table.selection()[0])['values'][0] if self.table.selection() else None
        pre_refresh_yview = self.table.yview()
        self._run_in_thread(self.manager.get_all_calls, lambda s, r: self._on_update_table_data_fetched(s, r, update_behavior, target_id, was_added, pre_selection_id, pre_refresh_yview, clear_fields), self.sort_column, self.sort_direction)
        
    def _on_update_table_data_fetched(self, success, all_calls, update_behavior, target_id, was_added, pre_selection_id, pre_refresh_yview, clear_fields):
        if not success: return

        self.table.unbind("<<TreeviewSelect>>")
        self.table.delete(*self.table.get_children())

        item_map = {}
        filter_text = self.search_var.get().lower().strip()
        display_keys = list(self.columns.keys())
        
        current_calls = set()
        new_high_priority = False
        new_standard_call = False
        now = datetime.now()

        for call_row in all_calls:
            call = dict(call_row)
            if call.get('Deleted'): continue
            
            report_id = call.get('ReportID')
            current_calls.add(report_id)
            
            if not self.is_first_load and report_id not in self.known_calls:
                db_code = call.get('Code', "")
                if db_code in self.high_priority_codes: new_high_priority = True
                else: new_standard_call = True

            if filter_text and not any(filter_text in str(v).lower() for v in call.values()): continue
            
            is_res = str(call.get('ResolutionStatus', "False")).lower() in ('1', 'true')
            is_canc = str(call.get('Cancelled', "False")).lower() in ('1', 'true')
            is_hp = call.get('Code', "") in self.high_priority_codes
            
            # SLA CALCULATIONS
            try:
                call_dt = datetime.strptime(f"{call['CallDate']} {call['CallTime']}", "%Y-%m-%d %H:%M")
                minutes_open = (now - call_dt).total_seconds() / 60
            except:
                minutes_open = 0
            
            tags = []
            if is_canc:
                tags.append("cancelled")
                call["TimeOpen"] = "Cancelled"
            elif is_res:
                tags.append("resolved")
                call["TimeOpen"] = "Closed"
            else:
                call["TimeOpen"] = f"{int(minutes_open)} min"
                
                # Critical SLA: Unresolved for 30+ minutes
                if minutes_open >= 30: 
                    tags.append("sla_critical")
                elif is_hp: 
                    tags.append("high_priority")
                else:
                    db_code = call.get('Code', "")
                    tags.append("nocode" if not db_code or db_code.lower() == "no_code" else "hascode")
            
            values = []
            for key in display_keys:
                if key in ("ResolutionStatus", "Cancelled"):
                    values.append("True" if str(call.get(key)).lower() in ('1', 'true') else "False")
                elif key == "TimeOpen":
                    values.append(call.get(key))
                else:
                    values.append(self._sanitize_for_tkinter(call.get(key, "")))
            
            item_id = self.table.insert("", tk.END, values=values, tags=tags)
            item_map[values[0]] = item_id

        self.known_calls = current_calls
        
        # Trigger audio alerts safely on the background thread
        if new_high_priority: self.executor.submit(self._play_siren)
        elif new_standard_call: self.executor.submit(self._play_ping)
        self.is_first_load = False

        if update_behavior == 'focus':
            if target_id and target_id in item_map:
                self.table.selection_set(item_map[target_id])
                self.table.focus(item_map[target_id])
                self.table.see(item_map[target_id])
            if was_added: self.clear_input_fields()
        elif update_behavior == 'scroll_to_end':
            if pre_selection_id and pre_selection_id in item_map: self.table.selection_set(item_map[pre_selection_id])
            if self.table.get_children(): self.table.see(self.table.get_children()[-1])
        else:
            if pre_selection_id and pre_selection_id in item_map: self.table.selection_set(item_map[pre_selection_id])
            if pre_refresh_yview and pre_refresh_yview[0] is not None: self.root.after(10, self.table.yview_moveto, pre_refresh_yview[0])
                
        if clear_fields and not self.is_dirty: self.clear_input_fields()
        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)

    def on_search(self, event=None): self.update_table(update_behavior='preserve')

    def start_auto_refresh(self):
        """Continuous poller to check the database for updates from other laptops."""
        self._auto_refresh_job = self.root.after(self.auto_refresh_interval_ms, self._auto_refresh_task)

    def _auto_refresh_task(self):
        self.executor.submit(self._check_network_for_updates)

    def _check_network_for_updates(self):
        try:
            current_count = self.manager.check_if_updated()
            now = datetime.now()
            
            # Force table redraw if DB changed OR if 60 seconds passed (to update visual SLA Timers)
            if current_count > self.last_update_count or (now - self.last_redraw_time).total_seconds() >= 60:
                self.last_update_count = current_count
                self.last_redraw_time = now
                if self.auto_scroll_var.get(): 
                    self.root.after(0, lambda: self.update_table(update_behavior='scroll_to_end'))
                else: 
                    self.root.after(0, lambda: self.update_table(update_behavior='preserve'))
        except Exception as e:
            self.logger.error(f"Network sync check failed: {e}")
        finally:
            self.start_auto_refresh()

    def open_passdown_notes(self):
        self._run_in_thread(self.manager.get_passdown_notes, self._on_passdown_fetched)
        
    def _on_passdown_fetched(self, success, notes):
        pd_win = tk.Toplevel(self.root)
        pd_win.title("Shift Passdown Notes")
        pd_win.geometry("600x400")
        
        note_display = scrolledtext.ScrolledText(pd_win, width=70, height=15, state="normal")
        note_display.pack(padx=10, pady=10, fill='both', expand=True)
        
        if notes:
            for n in reversed(notes):
                note_display.insert(tk.END, f"[{n['Timestamp']}] {n['User']}:\n{n['Note']}\n{'-'*50}\n")
        note_display.configure(state="disabled")
        note_display.see(tk.END)
        
        input_frame = ttk.Frame(pd_win)
        input_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        new_note = ttk.Entry(input_frame)
        new_note.pack(side="left", fill='x', expand=True, padx=(0, 5))
        
        def save_note():
            val = new_note.get().strip()
            if val:
                self.manager.add_passdown_note(self.current_user, val)
                pd_win.destroy()
                self.open_passdown_notes() # Refresh instantly
                
        ttk.Button(input_frame, text="Add Note", command=save_note).pack(side="right")

    def view_call_history(self):
        if not self.table.selection(): return
        report_id = self.table.item(self.table.selection()[0])["values"][0]
        self._run_in_thread(self.manager.get_history_for_call, lambda s, r: self._on_history_fetched(s, r, report_id), report_id)

    def _on_history_fetched(self, success, records, report_id):
        history_window = tk.Toplevel(self.root)
        history_window.title(f"History for Call {report_id}")
        history_text = scrolledtext.ScrolledText(history_window, width=80, height=20, state="normal")
        history_text.pack(padx=10, pady=10, expand=True, fill='both')
        if not success or not records: history_text.insert(tk.END, "No history found.")
        else:
            for record in records:
                details = f" | Details: {record['Details']}" if record['Details'] else ""
                history_text.insert(tk.END, f"[{record['Timestamp']}] User: {record['User']} | Action: {record['Action']}{details}\n")
        history_text.configure(state="disabled")

    def on_close(self):
        if self.is_dirty and not messagebox.askyesno("Exit", "Are you sure you want to exit?"): return
        if hasattr(self, '_auto_refresh_job'): self.root.after_cancel(self._auto_refresh_job)
        self.executor.shutdown(wait=False)
        self.manager.close()
        self.root.destroy()