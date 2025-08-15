import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from data_manager import DataManager
from datetime import datetime
import os
import sys
import logging
import configparser
import csv
import threading

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip:
            return
            
        x = event.x_root + 20
        y = event.y_root + 10
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{int(x)}+{int(y)}")
        
        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", 
                         borderwidth=1, font=("tahoma", "8", "normal"),
                         wraplength=300, justify='left')
        label.pack(ipadx=2, ipady=2)

    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
        self.tooltip = None

class ScrolledTextHandler(logging.Handler):
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
        self.root.title("Dispatch Call Management System")
        self.root.resizable(True, True)
        self.config = configparser.ConfigParser()
        self.load_config()
        self.current_user = None
        self.current_user_role = None
        self.is_dirty = False
        self.is_loading_data = False
        if not self.ensure_user_logged_in():
            self.root.destroy()
            return
        self._build_main_ui()
        self.root.deiconify()
        
    def _build_main_ui(self):
        self.show_deleted = False
        self.sort_column = "ReportID"
        self.sort_direction = "ASC"
        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.code_var = tk.StringVar()
        
        self.answered_status_var = tk.BooleanVar(value=False)
        self.answered_by_var = tk.StringVar()
        
        self.resolution_status_var = tk.BooleanVar(value=False)
        self.resolved_by_var = tk.StringVar()

        self.code_description_var = tk.StringVar()
        self.create_status_bar()
        self.create_log_area()
        self.setup_logging_handler()
        self.status_var.set(f"User: {self.current_user} ({self.current_user_role})")
        self.logger.info(f"User '{self.current_user}' logged in as '{self.current_user_role}'. Building UI.")
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
        self.start_backup_timer()
        self.start_auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        self.config.read('config.ini')
        self.auto_refresh_interval_ms = self.config.getint('APPLICATION', 'auto_refresh_seconds', fallback=30) * 1000
        
        self.auto_scroll_var = tk.BooleanVar(
            value=self.config.getboolean('APPLICATION', 'auto_scroll_to_latest', fallback=True)
        )

        self.max_backups = self.config.getint('BACKUP', 'max_backups', fallback=10)
        
        self.code_descriptions = dict(self.config.items('CODES')) if self.config.has_section('CODES') else {}
        if not self.code_descriptions:
            self.code_descriptions = {"no_code": "No specific code assigned."}
        
        self.display_to_config_map = {key.split('|')[0].strip(): key for key in self.config.options('CODES')}
        self.config_to_display_map = {v: k for k, v in self.display_to_config_map.items()}

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
            messagebox.showerror("Configuration Error", "[USERS] section not found in config.ini. Cannot start.")
            return False
        while not self.current_user:
            username = simpledialog.askstring("Login", "Enter your username:", parent=self.root)
            if username is None:
                self.logger.warning("Login cancelled by user. Shutting down.")
                return False
            user = username.strip().lower()
            if user in users:
                self.current_user = user
                self.current_user_role = users[user]
                return True
            else:
                messagebox.showwarning("Login Failed", "Invalid username.", parent=self.root)
        return True

    def _apply_permissions(self):
        is_admin = self.current_user_role == 'admin'
        admin_state = "normal" if is_admin else "disabled"
        self.delete_button.config(state=admin_state)
        self.restore_button.config(state=admin_state)
        self.file_menu.entryconfig("Change User", state=admin_state)

    def _setup_keyboard_shortcuts(self):
        self.root.bind('<Control-s>', lambda event: self.modify_call())
        self.root.bind('<Control-n>', lambda event: self.clear_input_fields())
        self.root.bind('<Delete>', lambda event: self.delete_call() if self.delete_button['state'] == 'normal' else None)

    def _set_dirty_flag(self, *args):
        if self.is_loading_data: return
        self.is_dirty = True

    def _setup_dirty_tracking(self):
        self.caller_var.trace_add("write", self._set_dirty_flag)
        self.location_var.trace_add("write", self._set_dirty_flag)
        self.code_var.trace_add("write", self._set_dirty_flag)
        self.answered_status_var.trace_add("write", self._set_dirty_flag)
        self.resolved_by_var.trace_add("write", self._set_dirty_flag)
        self.resolution_status_var.trace_add("write", self._set_dirty_flag)
        self.resolved_by_var.trace_add("write", self._set_dirty_flag)
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
        self.file_menu.add_command(label="Change User", command=self.change_user)
        self.file_menu.add_command(label="Export Report to CSV", command=self.export_report)
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
        
        formatted_codes = list(self.display_to_config_map.keys())
        ttk.Label(fields_frame, text="Code:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        code_cb = ttk.Combobox(fields_frame, textvariable=self.code_var, state="readonly", values=formatted_codes, width=uniform_width)
        code_cb.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        code_cb.bind("<<ComboboxSelected>>", self.update_code_description)
        
        no_code_display = self.config_to_display_map.get("no_code", "No Code")
        if no_code_display in formatted_codes:
            self.code_var.set(no_code_display)
        elif formatted_codes:
            self.code_var.set(formatted_codes[0])

        ttk.Label(fields_frame, text="Code Desc:").grid(row=3, column=2, padx=5, pady=2, sticky="w")
        ttk.Label(fields_frame, textvariable=self.code_description_var, wraplength=400, justify="left").grid(row=3, column=3, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Label(fields_frame, text="Description:").grid(row=4, column=0, padx=5, pady=2, sticky="nw")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, height=5, width=60, borderwidth=0)
        self.description_entry.grid(row=4, column=1, columnspan=4, padx=5, pady=2, sticky="w")
        
        # New "Answered" section
        ttk.Checkbutton(fields_frame, text="Answered", variable=self.answered_status_var, command=self.toggle_answered_entry).grid(row=5, column=0, padx=5, pady=5, sticky="w")
        answered_frame = ttk.Frame(fields_frame)
        answered_frame.grid(row=5, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(answered_frame, text="Answered By:").pack(side="left", padx=(0, 5))
        self.answered_by_entry = ttk.Entry(answered_frame, textvariable=self.answered_by_var, state="disabled", width=uniform_width)
        self.answered_by_entry.pack(side="left")

        # Original "Resolved" section
        ttk.Checkbutton(fields_frame, text="Resolved", variable=self.resolution_status_var, command=self.toggle_resolved_entry).grid(row=6, column=0, padx=5, pady=5, sticky="w")
        resolved_frame = ttk.Frame(fields_frame)
        resolved_frame.grid(row=6, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(resolved_frame, text="Resolved By:").pack(side="left", padx=(0, 5))
        self.resolved_by_entry = ttk.Entry(resolved_frame, textvariable=self.resolved_by_var, state="disabled", width=uniform_width)
        self.resolved_by_entry.pack(side="left")

        self.update_code_description()

    def update_source_options(self, event=None):
        medium = self.input_medium_var.get()
        options = self.source_options.get(medium, [])
        self.source_cb['values'] = options
        self.source_var.set(options[0] if options else "")

    def create_buttons(self):
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.add_button = ttk.Button(buttons_frame, text="Add Call", command=self.add_call)
        self.add_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.add_button, "Add a new call with the details above.")
        
        self.save_button = ttk.Button(buttons_frame, text="Save Modification", command=self.modify_call)
        self.save_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.save_button, "Save changes to the selected call (Ctrl+S).")
        
        self.delete_button = ttk.Button(buttons_frame, text="Delete Call", command=self.delete_call)
        self.delete_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.delete_button, "Mark the selected call as deleted (Delete).\n(Admin only)")
        
        self.clear_button = ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_input_fields)
        self.clear_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.clear_button, "Clear all input fields (Ctrl+N).")
        
        self.red_flag_button = ttk.Button(buttons_frame, text="Red Flag", command=self.red_flag_call)
        self.red_flag_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.red_flag_button, "Toggle a red flag on the selected call.")
        
        self.toggle_deleted_button = ttk.Button(buttons_frame, text="Show Deleted", command=self.toggle_deleted)
        self.toggle_deleted_button.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(self.toggle_deleted_button, "Toggle visibility of deleted calls.")
        
        self.restore_button = ttk.Button(buttons_frame, text="Restore Call", command=self.restore_call)
        self.restore_button.grid(row=0, column=6, padx=5, pady=5)
        ToolTip(self.restore_button, "Restore a call that was marked as deleted.\n(Admin only)")
        
        self.history_button = ttk.Button(buttons_frame, text="View History", command=self.view_call_history)
        self.history_button.grid(row=0, column=7, padx=5, pady=5)
        ToolTip(self.history_button, "View the audit history for the selected call.")

        self.action_buttons = [
            self.add_button, self.save_button, self.delete_button, self.clear_button, 
            self.red_flag_button, self.toggle_deleted_button, self.restore_button, self.history_button
        ]

    def _on_manual_scroll(self, event=None):
        self.auto_scroll_var.set(False)

    def create_table(self):
        self.columns = {
            "ReportID": ("Call ID", 80), "CallDate": ("Date", 80), "CallTime": ("Time", 60),
            "AnsweredTimestamp": ("Answered At", 120), "AnsweredStatus": ("Answered?", 70), "AnsweredBy": ("Answered By", 100),
            "ResolutionTimestamp": ("Resolved At", 120), "ResolutionStatus": ("Resolved?", 70), "ResolvedBy": ("Resolved By", 100),
            "InputMedium": ("Medium", 100), "Source": ("Source", 100), "Caller": ("Caller", 100),
            "Location": ("Location", 120), "Code": ("Code", 150), "Description": ("Description", 300),
            "CreatedBy": ("Created By", 100), "ModifiedBy": ("Modified By", 100), "ReportNumber": ("Report #", 100)
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
        
        self.table.tag_configure("answered", background="#f5f5dc")
        self.table.tag_configure("resolved", background="#d0f0c0")
        self.table.tag_configure("redflag", background="#f08080")
        self.table.tag_configure("deleted", foreground="#a9a9a9")
        
        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)
        
        self.table.bind("<MouseWheel>", self._on_manual_scroll)
        self.scrollbar.bind("<ButtonPress-1>", self._on_manual_scroll)
        self.scrollbar.bind("<B1-Motion>", self._on_manual_scroll)
        
        self.table.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

    def sort_table(self, col):
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
        ToolTip(scroll_check, "If checked, the table will automatically scroll to the latest entry during a refresh.")

    def configure_grid_weights(self):
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def update_code_description(self, event=None):
        display_key = self.code_var.get()
        config_key = self.display_to_config_map.get(display_key)
        description = self.code_descriptions.get(config_key, "Unknown Code").split('|', 1)[-1].strip()
        self.code_description_var.set(description)

    def toggle_answered_entry(self):
        state = "normal" if self.answered_status_var.get() else "disabled"
        self.answered_by_entry.configure(state=state)
        if state == "disabled": self.answered_by_var.set("")

    def toggle_resolved_entry(self):
        state = "normal" if self.resolution_status_var.get() else "disabled"
        self.resolved_by_entry.configure(state=state)
        if state == "disabled": self.resolved_by_var.set("")

    def _set_ui_busy(self, is_busy):
        """Disables or enables action buttons and updates the status bar."""
        state = "disabled" if is_busy else "normal"
        for button in self.action_buttons:
            button.config(state=state)
        
        if is_busy:
            self.status_var.set("Working...")
        else:
            self.status_var.set("Ready")
            self._apply_permissions()
            if self.table.selection():
                self.add_button.config(state="disabled")

    def _validate_fields(self):
        if not self.caller_var.get().strip():
            messagebox.showwarning("Validation Error", "Caller ID cannot be empty.")
            return False
        if not self.location_var.get().strip():
            messagebox.showwarning("Validation Error", "Location cannot be empty.")
            return False
        if not self.description_entry.get("1.0", tk.END).strip():
            messagebox.showwarning("Validation Error", "Description cannot be empty.")
            return False
        if self.answered_status_var.get() and not self.answered_by_var.get().strip():
            messagebox.showwarning("Validation Error", "'Answered By' cannot be empty when marking as answered.")
            return False
        if self.resolution_status_var.get() and not self.resolved_by_var.get().strip():
            messagebox.showwarning("Validation Error", "'Resolved By' cannot be empty when marking as resolved.")
            return False
        return True

    def _run_in_thread(self, target, callback, *args):
        self._set_ui_busy(True)
        def worker():
            try:
                result = target(*args)
                if self.root.winfo_exists(): self.root.after(0, callback, True, result)
            except Exception as e:
                if self.root.winfo_exists(): self.root.after(0, callback, False, e)
            finally:
                if self.root.winfo_exists():
                    self.root.after(0, self._set_ui_busy, False)
        threading.Thread(target=worker, daemon=True).start()

    def add_call(self):
        if not self._validate_fields(): return
        raw_code = self.display_to_config_map.get(self.code_var.get(), "")
        call_data = {
            "InputMedium": self.input_medium_var.get(), "Source": self.source_var.get(),
            "Caller": self.caller_var.get().strip(), "Location": self.location_var.get().strip(),
            "Code": raw_code, "Description": self.description_entry.get("1.0", tk.END).strip(),
            "AnsweredStatus": self.answered_status_var.get(), "AnsweredBy": self.answered_by_var.get().strip(),
            "ResolutionStatus": self.resolution_status_var.get(), "ResolvedBy": self.resolved_by_var.get().strip()
        }
        self._run_in_thread(self.manager.add_call, self._on_add_call_complete, call_data, self.current_user)

    def _on_add_call_complete(self, success, new_report_id):
        if success:
            self.logger.info(f"Call added: {new_report_id}")
            self.is_dirty = False
            self.update_table(update_behavior='focus', target_id=new_report_id, was_added=True)
        else:
            self.logger.error(f"Failed to add call: {new_report_id}")
            messagebox.showerror("Database Error", f"Failed to add call: {new_report_id}")

    def modify_call(self):
        if not self.table.selection():
            messagebox.showwarning("Selection Error", "No call selected to modify.")
            return
        if not self._validate_fields(): return
        report_id = self.table.item(self.table.selection()[0])["values"][0]
        raw_code = self.display_to_config_map.get(self.code_var.get(), "")
        updated_call = {
            "InputMedium": self.input_medium_var.get(), "Source": self.source_var.get(),
            "Caller": self.caller_var.get().strip(), "Location": self.location_var.get().strip(),
            "Code": raw_code, "Description": self.description_entry.get("1.0", tk.END).strip(),
            "AnsweredStatus": self.answered_status_var.get(), "AnsweredBy": self.answered_by_var.get().strip(),
            "ResolutionStatus": self.resolution_status_var.get(), "ResolvedBy": self.resolved_by_var.get().strip()
        }
        self._run_in_thread(self.manager.modify_call, self._on_modify_call_complete, report_id, updated_call, self.current_user)

    def _on_modify_call_complete(self, success, result_or_error):
        if success:
            if self.table.selection():
                report_id = self.table.item(self.table.selection()[0])["values"][0]
                self.logger.info(f"Call modified: {report_id}")
            self.is_dirty = False
            self.update_table(clear_fields=True)
        else:
            self.logger.error(f"Failed to modify call: {result_or_error}")
            messagebox.showerror("Database Error", f"Failed to modify call: {result_or_error}")

    def _perform_call_action(self, action_func, confirm_msg, success_log):
        if not self.table.selection():
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        report_id = self.table.item(self.table.selection()[0])["values"][0]
        if confirm_msg and not messagebox.askyesno("Confirm Action", confirm_msg.format(report_id)):
            return
        self._run_in_thread(action_func, lambda s, r: self._on_generic_action_complete(s, r, success_log.format(report_id)), report_id, self.current_user)

    def _on_generic_action_complete(self, success, result_or_error, log_message):
        if success:
            self.logger.info(log_message)
            self.is_dirty = False
            self.clear_input_fields()
            self.update_table()
        else:
            self.logger.error(f"Action failed: {result_or_error}")
            messagebox.showerror("Error", f"Action failed: {result_or_error}")

    def delete_call(self): self._perform_call_action(self.manager.delete_call, "Are you sure you want to delete call {0}?", "Call marked as deleted: {0}")
    def restore_call(self): self._perform_call_action(self.manager.restore_call, "Are you sure you want to restore call {0}?", "Call restored: {0}")
    def red_flag_call(self): self._perform_call_action(self.manager.red_flag_call, None, "Red-flag status toggled for call: {0}")

    def load_selected_call(self, event):
        if self.is_dirty:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes that will be lost. Discard them?"):
                return "break"
        if not self.table.selection(): return
        
        self.add_button.config(state="disabled")

        item = self.table.item(self.table.selection()[0])
        call = dict(zip(self.columns.keys(), item['values']))
        self.is_loading_data = True
        try:
            self.input_medium_var.set(call.get("InputMedium", ""))
            self.update_source_options()
            self.source_var.set(call.get("Source", ""))
            self.caller_var.set(call.get("Caller", ""))
            self.location_var.set(call.get("Location", ""))
            
            db_code = self.display_to_config_map.get(call.get("Code", ""), call.get("Code", ""))
            display_code = self.config_to_display_map.get(db_code, db_code)
            self.code_var.set(display_code)

            self.update_code_description()
            self.description_entry.delete("1.0", tk.END)
            self.description_entry.insert(tk.END, call.get("Description", ""))

            # New answered fields
            is_answered = str(call.get("AnsweredStatus", "False")).lower() in ('true', '1')
            self.answered_status_var.set(is_answered)
            self.toggle_answered_entry()
            self.answered_by_var.set(call.get("AnsweredBy", ""))

            # Original resolved fields
            is_resolved = str(call.get("ResolutionStatus", "False")).lower() in ('true', '1')
            self.resolution_status_var.set(is_resolved)
            self.toggle_resolved_entry()
            self.resolved_by_var.set(call.get("ResolvedBy", ""))

        finally:
            self.is_loading_data = False
        self.is_dirty = False

    def toggle_deleted(self):
        self.show_deleted = not self.show_deleted
        self.status_var.set("Showing all calls (including deleted)" if self.show_deleted else "Showing only active calls")
        self.update_table()

    def clear_input_fields(self):
        if self.is_dirty and not messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?"):
            return
        self.is_loading_data = True
        try:
            self.table.selection_remove(self.table.selection())
            self.caller_var.set("")
            self.location_var.set("")
            self.description_entry.delete("1.0", tk.END)
            
            self.answered_status_var.set(False)
            self.answered_by_var.set("")
            self.toggle_answered_entry()

            self.resolution_status_var.set(False)
            self.resolved_by_var.set("")
            self.toggle_resolved_entry()

            no_code_display = self.config_to_display_map.get("no_code", "")
            if no_code_display: self.code_var.set(no_code_display)

            self.update_code_description()
            
            self.add_button.config(state="normal")
        finally:
            self.is_loading_data = False
        self.is_dirty = False

    def export_report(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename: return
        self._run_in_thread(self.manager.get_all_calls, 
                             lambda s, r: self._on_export_data_fetched(s, r, filename), 
                             self.sort_column, self.sort_direction)

    def _on_export_data_fetched(self, success, calls, filename):
        if not success:
            messagebox.showerror("Export Error", f"Failed to fetch data for export: {calls}")
            return
        if not calls:
            messagebox.showinfo("Export Report", "No calls to export.")
            return
        try:
            fieldnames = calls[0].keys()
            with open(filename, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for call in calls:
                    writer.writerow(dict(call))
            self.logger.info(f"Report exported to {filename}")
            messagebox.showinfo("Export Successful", f"Report successfully exported to\n{filename}")
        except Exception as e:
            self.logger.error(f"Failed to export report: {e}")
            messagebox.showerror("Export Error", f"Failed to write report file: {e}")
            
    def change_user(self):
        if self.is_dirty and not messagebox.askyesno("Unsaved Changes", "You have unsaved changes that will be lost. Continue?"):
            return
        original_user = self.current_user
        self.current_user = None 
        if self.ensure_user_logged_in():
            if self.current_user != original_user:
                self.status_var.set(f"User changed to: {self.current_user} ({self.current_user_role})")
                self.logger.info(f"User changed from '{original_user}' to: {self.current_user}")
                self._apply_permissions()
                self.clear_input_fields()
        else:
            self.current_user = original_user

    def update_table(self, update_behavior='preserve', target_id=None, was_added=False, clear_fields=False):
        pre_selection_id = None
        if self.table.selection():
            pre_selection_id = self.table.item(self.table.selection()[0])['values'][0]

        pre_refresh_yview = self.table.yview()

        callback = lambda s, r: self._on_update_table_data_fetched(
            s, r, update_behavior, target_id, was_added, pre_selection_id, pre_refresh_yview, clear_fields
        )
        
        self._run_in_thread(
            self.manager.get_all_calls, 
            callback, 
            self.sort_column, 
            self.sort_direction
        )
        
    def _on_update_table_data_fetched(self, success, all_calls, update_behavior, target_id, was_added, pre_selection_id, pre_refresh_yview, clear_fields):
        if not success:
            self.logger.error(f"Failed to fetch table data for update: {all_calls}")
            return

        self.table.unbind("<<TreeviewSelect>>")
        self.table.delete(*self.table.get_children())

        item_map = {}
        filter_text = self.search_var.get().lower().strip()

        for call_row in all_calls:
            call = dict(call_row)
            if not self.show_deleted and call.get('Deleted'): continue
            if filter_text and not any(filter_text in str(v).lower() for v in call.values()): continue
            
            tags = []
            if call.get('AnsweredStatus'): tags.append("answered")
            if call.get('ResolutionStatus'): tags.append("resolved")
            if call.get('RedFlag'): tags.append("redflag")
            if call.get('Deleted'): tags.append("deleted")
            
            values = [call.get(col, "") for col in self.columns.keys()]
            values[4] = "True" if values[4] else "False"
            values[7] = "True" if values[7] else "False"
            db_code = values[13] 
            values[13] = self.config_to_display_map.get(db_code, db_code) 
            
            item_id = self.table.insert("", tk.END, values=values, tags=tags)
            item_map[values[0]] = item_id

        if update_behavior == 'focus':
            if target_id and target_id in item_map:
                item_to_focus = item_map[target_id]
                self.table.selection_set(item_to_focus)
                self.table.focus(item_to_focus)
                self.table.see(item_to_focus)
            if was_added:
                self.clear_input_fields()
        
        elif update_behavior == 'scroll_to_end':
            if pre_selection_id and pre_selection_id in item_map:
                self.table.selection_set(item_map[pre_selection_id])
            
            if self.table.get_children():
                last_item = self.table.get_children()[-1]
                self.table.see(last_item)
        
        else: # 'preserve' behavior
            if pre_selection_id and pre_selection_id in item_map:
                self.table.selection_set(item_map[pre_selection_id])
            
            if pre_refresh_yview and pre_refresh_yview[0] is not None:
                self.root.after(10, self.table.yview_moveto, pre_refresh_yview[0])
                
        if clear_fields:
            self.clear_input_fields()
        
        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)

    def on_search(self, event=None): self.update_table(update_behavior='preserve')
    
    def start_backup_timer(self): self.root.after(900 * 1000, self.create_backup)

    def create_backup(self):
        self._run_in_thread(self.manager.create_backup, self._on_backup_complete, "backups", self.max_backups)

    def _on_backup_complete(self, success, result_or_error):
        try:
            if success: self.logger.info(result_or_error)
            else: self.logger.error(f"Scheduled backup failed: {result_or_error}")
        finally:
            self.start_backup_timer()

    def start_auto_refresh(self):
        self._auto_refresh_job = self.root.after(self.auto_refresh_interval_ms, self._auto_refresh_task)

    def _auto_refresh_task(self):
        if self.is_dirty:
            self.logger.debug("Auto-refresh skipped due to unsaved changes in the form.")
        else:
            self.logger.debug("Performing automatic table refresh.")
            if self.auto_scroll_var.get():
                self.update_table(update_behavior='scroll_to_end')
            else:
                self.update_table(update_behavior='preserve')
        
        self.start_auto_refresh()

    def view_call_history(self):
        if not self.table.selection():
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        report_id = self.table.item(self.table.selection()[0])["values"][0]
        self._run_in_thread(self.manager.get_history_for_call, lambda s, r: self._on_history_fetched(s, r, report_id), report_id)

    def _on_history_fetched(self, success, records, report_id):
        history_window = tk.Toplevel(self.root)
        history_window.title(f"History for Call {report_id}")
        history_text = scrolledtext.ScrolledText(history_window, width=80, height=20, state="normal")
        history_text.pack(padx=10, pady=10, expand=True, fill='both')
        if not success:
            history_text.insert(tk.END, f"Could not retrieve history: {records}")
        elif not records:
            history_text.insert(tk.END, "No history found for this call.")
        else:
            for record in records:
                details = f" | Details: {record['Details']}" if record['Details'] else ""
                line = f"[{record['Timestamp']}] User: {record['User']} | Action: {record['Action']}{details}\n"
                history_text.insert(tk.END, line)
        history_text.configure(state="disabled")

    def on_close(self):
        if self.is_dirty and not messagebox.askyesno("Exit", "You have unsaved changes. Are you sure you want to exit?"):
            return
        
        if hasattr(self, '_auto_refresh_job'):
            self.root.after_cancel(self._auto_refresh_job)
            
        self.logger.info("Application closing.")
        self.manager.close()
        self.root.destroy()