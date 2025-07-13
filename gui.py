import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from dispatch_call_manager import DispatchCallManager
from utils import calculate_file_hash, get_file_modification_time
from datetime import datetime
import os
import sys
from threading import Timer, Thread
import time

class DispatchCallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dispatch Call Management System")
        self.root.resizable(True, True)

        self.manager = DispatchCallManager()
        self.last_loaded_hash = None
        self.backup_counter = 1
        self.max_backups = 10
        self.show_deleted = False
        self.has_unsaved_changes = False
        self.autosave_file = "autosave.bin"
        self.last_file_mtime = 0
        self.watching_autosave = False

        # Tkinter variables
        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.code_var = tk.StringVar(value="No_Code")
        self.resolution_status_var = tk.BooleanVar(value=False)
        self.resolved_by_var = tk.StringVar()

        # Source options based on Input Medium
        self.source_options = {
            "Radio": ["Safety", "General", "First Aid"],
            "Social Media": ["Discord", "Phone Call", "SMS"]
        }

        self.code_descriptions = {
            "Signal_13 | MAYDAY": "Immediate personal danger.",
            "No_Code": "General situations.",
            "Green": "Supervisor backup.",
            "Orange": "Hazardous material.",
            "Red": "Suspected fire.",
            "Blue": "Life threatening medical emergency.",
            "Yellow": "Attendee unable to walk due to minor medical issue.",
            "Yellow M": "Mental health crisis.",
            "Purple": "Harassment, unwanted attention, or contact.",
            "Silver": "Active assailant.",
            "Adam": "Lost child.",
            "Black": "Suspicious package or call threat."
        }
        self.code_description_var = tk.StringVar(
            value=self.code_descriptions[self.code_var.get()]
        )

        # Build UI
        self.create_status_bar()
        self.create_log_area()
        self.ensure_user_logged_in()
        self.create_table()
        self.load_autosave()
        self.create_menu_bar()
        self.create_input_fields()
        self.create_buttons()
        self.create_search_bar()
        self.configure_grid_weights()

        # Start periodic backups and autosave watcher
        self.start_backup_timer()
        self.start_autosave_watcher()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                              relief=tk.SUNKEN, anchor="w")
        status_bar.grid(row=5, column=0, columnspan=2, sticky="ew")

    def create_log_area(self):
        """Create the logging text area."""
        self.log_area = scrolledtext.ScrolledText(self.root,
                                               height=5, state="disabled")
        self.log_area.grid(row=4, column=0, columnspan=2,
                         sticky="nsew", padx=10, pady=10)

    def log(self, message):
        """Add a message to the log area."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.configure(state="disabled")
        self.log_area.see(tk.END)

    def ensure_user_logged_in(self):
        """Ensure a user is logged in before proceeding."""
        while not self.manager.current_user:
            username = simpledialog.askstring("Login", "Enter your username:")
            if username is None:
                self.root.destroy()
                return
            if username.strip():
                self.manager.set_user(username.strip())
                self.status_var.set(f"User: {username.strip()}")
                self.log(f"User set to: {username.strip()}")
            else:
                messagebox.showwarning("Invalid Input", "Username cannot be empty.")

    def create_menu_bar(self):
        """Create the menu bar at the top of the window."""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save", command=self.save_data)
        file_menu.add_command(label="Load", command=self.load_data)
        file_menu.add_separator()
        file_menu.add_command(label="Change User", command=self.change_user)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    def create_input_fields(self):
        """Create the input fields for new dispatch calls."""
        fields_frame = ttk.LabelFrame(self.root, text="New Dispatch Call")
        fields_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Input Medium
        ttk.Label(fields_frame, text="Input Medium:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        input_medium_cb = ttk.Combobox(fields_frame, textvariable=self.input_medium_var, state="readonly", width=12)
        input_medium_cb['values'] = ["Radio", "Social Media"]
        input_medium_cb.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        input_medium_cb.bind("<<ComboboxSelected>>", lambda e: self.update_source_options())

        # Source
        ttk.Label(fields_frame, text="Source:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.source_cb = ttk.Combobox(fields_frame, textvariable=self.source_var, state="readonly", width=12)
        self.source_cb.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.update_source_options()

        # Caller ID
        ttk.Label(fields_frame, text="Caller ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        caller_entry = ttk.Entry(fields_frame, textvariable=self.caller_var, width=14)
        caller_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Location
        ttk.Label(fields_frame, text="Location:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        location_entry = ttk.Entry(fields_frame, textvariable=self.location_var, width=14)
        location_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Code
        ttk.Label(fields_frame, text="Code:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        code_cb = ttk.Combobox(fields_frame, textvariable=self.code_var, state="readonly", width=12)
        code_cb['values'] = list(self.code_descriptions.keys())
        code_cb.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        code_cb.bind("<<ComboboxSelected>>", lambda e: self.update_code_description())

        # Code Description
        ttk.Label(fields_frame, text="Code Description:").grid(row=3, column=2, padx=5, pady=5, sticky="nw")
        code_desc_label = ttk.Label(fields_frame, textvariable=self.code_description_var,
                                  wraplength=300, anchor="w", justify="left", width=40)
        code_desc_label.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        # Description
        ttk.Label(fields_frame, text="Description:").grid(row=4, column=0, padx=5, pady=5, sticky="nw")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, height=5, width=50)
        self.description_entry.grid(row=4, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        # Resolved checkbox + Resolved By
        resolved_chk = ttk.Checkbutton(fields_frame, text="Resolved",
                                     variable=self.resolution_status_var,
                                     command=self.toggle_resolver_entry)
        resolved_chk.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(fields_frame, text="Resolved By:").grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.resolved_by_entry = ttk.Entry(fields_frame, textvariable=self.resolved_by_var,
                                         state="disabled", width=14)
        self.resolved_by_entry.grid(row=5, column=2, padx=5, pady=5, sticky="w")

        # Initialize code description
        self.update_code_description()

    def update_source_options(self):
        """Update the source options based on the selected input medium."""
        medium = self.input_medium_var.get()
        options = self.source_options.get(medium, [])
        self.source_cb['values'] = options
        if options:
            self.source_var.set(options[0])
        else:
            self.source_var.set("")

    def create_buttons(self):
        """Create the action buttons."""
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        ttk.Button(buttons_frame, text="Add Call", command=self.add_call).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Resolve Call", command=self.resolve_call).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Save Modification", command=self.modify_call).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Delete Call", command=self.delete_call).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_input_fields).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Print Report", command=self.print_report).grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Red Flag", command=self.red_flag_call).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Show Deleted", command=self.toggle_deleted).grid(row=0, column=7, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Restore", command=self.restore_call).grid(row=0, column=8, padx=5, pady=5)

    def create_table(self):
        """Create the main table for displaying calls."""
        columns = [
            ("CallID", "Call ID"),
            ("CallDate", "Date"),
            ("CallTime", "Time"),
            ("ResolutionTimestamp", "Resolved At"),
            ("ResolutionStatus", "Resolved?"),
            ("InputMedium", "Input Medium"),
            ("Source", "Source"),
            ("Caller", "Caller"),
            ("Location", "Location"),
            ("Code", "Code"),
            ("Description", "Description"),
            ("ResolvedBy", "Resolved By"),
            ("CreatedBy", "Created By"),
            ("ModifiedBy", "Modified By"),
            ("ReportNumber", "Report Number")
        ]
        self.table = ttk.Treeview(self.root, columns=[col[0] for col in columns], show="headings")
        for col, heading in columns:
            self.table.heading(col, text=heading)
            if col == "Description":
                self.table.column(col, width=120, anchor="w")
            else:
                self.table.column(col, width=80, anchor="center")

        self.table.tag_configure("resolved", background="#d0f0c0")
        self.table.tag_configure("redflag", background="#f08080")
        self.table.tag_configure("deleted", background="#d3d3d3", foreground="#a9a9a9")

        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)
        self.table.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.update_table()

    def create_search_bar(self):
        """Create the search bar."""
        search_frame = ttk.Frame(self.root)
        search_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        self.search_var = tk.StringVar()
        self.search_label = ttk.Label(search_frame, text="Search:")
        self.search_label.grid(row=0, column=0, sticky="w")
        self.search_label.bind("<Button-1>", self.hidden_easter_egg)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.grid(row=0, column=1, padx=5, sticky="w")
        search_entry.bind("<KeyRelease>", lambda e: self.on_search())

    def configure_grid_weights(self):
        """Configure grid weights for proper resizing."""
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def hidden_easter_egg(self, event):
        """Easter egg functionality."""
        self.hidden_count = getattr(self, "hidden_count", 0) + 1
        if self.hidden_count == 5:
            messagebox.showinfo("Easter Egg", "You found the hidden cheesecake! - nhpha")
            self.hidden_count = 0

    def update_code_description(self):
        """Update the code description based on selected code."""
        code = self.code_var.get()
        desc = self.code_descriptions.get(code, "")
        self.code_description_var.set(desc)

    def toggle_resolver_entry(self):
        """Toggle the resolved by entry field based on checkbox state."""
        if self.resolution_status_var.get():
            self.resolved_by_entry.configure(state="normal")
        else:
            self.resolved_by_entry.configure(state="disabled")
            self.resolved_by_var.set("")

    def add_call(self):
        """Add a new dispatch call."""
        caller = self.caller_var.get().strip()
        description = self.description_entry.get("1.0", tk.END).strip()
        location = self.location_var.get().strip()

        if not caller:
            messagebox.showwarning("Validation Error", "Caller ID cannot be empty.")
            return
        if not location:
            messagebox.showwarning("Validation Error", "Location cannot be empty.")
            return
        if not description:
            messagebox.showwarning("Validation Error", "Description cannot be empty.")
            return

        call = {
            "InputMedium": self.input_medium_var.get(),
            "Source": self.source_var.get().strip(),
            "Caller": caller,
            "Location": location,
            "Code": self.code_var.get(),
            "Description": description,
            "ResolutionStatus": self.resolution_status_var.get(),
            "ResolvedBy": self.resolved_by_var.get().strip() if self.resolution_status_var.get() else ""
        }

        try:
            call_id = self.manager.add_call(call)
            self.log(f"Call added: {call_id}")
            self.status_var.set(f"Call {call_id} added.")
            self.has_unsaved_changes = True
            self.save_and_reload()
            self.clear_input_fields()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_and_reload(self):
        """Autosave to binary, text, and CSV; then reload from binary."""
        try:
            self.manager.save_to_file("autosave.bin", "bin")
            self.manager.save_to_file("autosave.txt", "txt")
            self.manager.save_to_file("autosave.csv", "csv")
            self.manager.load_from_file("autosave.bin", "bin")
            self.last_loaded_hash = self.manager._calculate_hash()
            self.update_table()
            self.log("Autosave completed and data reloaded.")
            self.status_var.set("Autosave complete.")
            self.has_unsaved_changes = False
            self.last_file_mtime = get_file_modification_time(self.autosave_file)
        except Exception as e:
            self.log(f"Error during autosave: {e}")
            messagebox.showerror("Autosave Error", str(e))

    def load_selected_call(self, event):
        """Load the selected call into the input fields."""
        selected = self.table.selection()
        if not selected:
            return
        call_id = self.table.item(selected[0])["values"][0]
        call = next((c for c in self.manager.calls if c["CallID"] == call_id), None)
        if not call:
            return

        # Populate form fields
        self.input_medium_var.set(call.get("InputMedium", ""))
        self.update_source_options()
        self.source_var.set(call.get("Source", ""))
        self.caller_var.set(call.get("Caller", ""))
        self.location_var.set(call.get("Location", ""))
        self.code_var.set(call.get("Code", ""))
        self.update_code_description()
        self.description_entry.delete("1.0", tk.END)
        self.description_entry.insert(tk.END, call.get("Description", ""))
        self.resolution_status_var.set(call.get("ResolutionStatus", False))
        self.toggle_resolver_entry()
        self.resolved_by_var.set(call.get("ResolvedBy", ""))

    def modify_call(self):
        """Modify an existing dispatch call."""
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        call_id = self.table.item(selected[0])["values"][0]
        caller = self.caller_var.get().strip()
        description = self.description_entry.get("1.0", tk.END).strip()
        location = self.location_var.get().strip()

        if not caller:
            messagebox.showwarning("Validation Error", "Caller ID cannot be empty.")
            return
        if not location:
            messagebox.showwarning("Validation Error", "Location cannot be empty.")
            return
        if not description:
            messagebox.showwarning("Validation Error", "Description cannot be empty.")
            return
        if self.resolution_status_var.get() and not self.resolved_by_var.get().strip():
            messagebox.showwarning("Validation Error", "Resolved By cannot be empty when marking as resolved.")
            return

        updated_call = {
            "InputMedium": self.input_medium_var.get(),
            "Source": self.source_var.get().strip(),
            "Caller": caller,
            "Location": location,
            "Code": self.code_var.get(),
            "Description": description,
            "ResolutionStatus": self.resolution_status_var.get(),
            "ResolvedBy": self.resolved_by_var.get().strip() if self.resolution_status_var.get() else ""
        }

        try:
            self.manager.modify_call(call_id, updated_call)
            self.log(f"Call modified: {call_id}")
            self.status_var.set(f"Call {call_id} modified.")
            self.has_unsaved_changes = True
            self.save_and_reload()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def resolve_call(self):
        """Mark a call as resolved."""
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        call_id = self.table.item(selected[0])["values"][0]
        resolved_by = simpledialog.askstring("Resolve Call", "Enter the name who resolved the call:")
        if not resolved_by or not resolved_by.strip():
            messagebox.showwarning("Validation Error", "Resolved By cannot be empty.")
            return

        try:
            self.manager.resolve_call(call_id, resolved_by.strip())
            self.log(f"Call resolved: {call_id} by {resolved_by.strip()}")
            self.status_var.set(f"Call {call_id} resolved.")
            self.has_unsaved_changes = True
            self.save_and_reload()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_call(self):
        """Delete a call (mark as deleted)."""
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        call_id = self.table.item(selected[0])["values"][0]
        confirm = messagebox.askyesno("Delete Confirmation", f"Are you sure you want to delete call {call_id}?")
        if not confirm:
            return
        try:
            self.manager.delete_call(call_id)
            self.log(f"Call marked as deleted: {call_id}")
            self.status_var.set(f"Call {call_id} deleted.")
            self.has_unsaved_changes = True
            self.save_and_reload()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def restore_call(self):
        """Restore a deleted call."""
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        call_id = self.table.item(selected[0])["values"][0]
        try:
            self.manager.restore_call(call_id)
            self.log(f"Call restored: {call_id}")
            self.status_var.set(f"Call {call_id} restored.")
            self.has_unsaved_changes = True
            self.save_and_reload()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def red_flag_call(self):
        """Toggle red flag status for a call."""
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "No call selected.")
            return
        call_id = self.table.item(selected[0])["values"][0]
        try:
            self.manager.red_flag_call(call_id)
            self.log(f"Call red-flag toggled: {call_id}")
            self.status_var.set(f"Call {call_id} red-flag status changed.")
            self.has_unsaved_changes = True
            self.save_and_reload()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_deleted(self):
        """Toggle showing deleted calls."""
        self.show_deleted = not self.show_deleted
        text = ("Showing all calls (including deleted)" if self.show_deleted 
                else "Showing only active calls")
        self.status_var.set(text)
        self.update_table()

    def clear_input_fields(self):
        """Clear all input fields."""
        self.input_medium_var.set("Radio")
        self.update_source_options()
        self.caller_var.set("")
        self.location_var.set("")
        self.code_var.set("No_Code")
        self.update_code_description()
        self.description_entry.delete("1.0", tk.END)
        self.resolution_status_var.set(False)
        self.resolved_by_var.set("")
        self.resolved_by_entry.configure(state="disabled")

    def print_report(self):
        """Print a report of calls to a file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filename:
            return
        include_deleted = messagebox.askyesno("Include Deleted", "Include deleted calls in report?")
        try:
            with open(filename, "w") as file:
                file.write("Dispatch Call Report\n")
                file.write("="*40 + "\n")
                for call in self.manager.calls:
                    if call.get("Deleted", False) and not include_deleted:
                        continue
                    file.write(f"Call ID: {call.get('CallID', '')}\n")
                    file.write(f"Date: {call.get('CallDate', '')}\n")
                    file.write(f"Time: {call.get('CallTime', '')}\n")
                    file.write(f"Caller: {call.get('Caller', '')}\n")
                    file.write(f"Location: {call.get('Location', '')}\n")
                    file.write(f"Code: {call.get('Code', '')}\n")
                    file.write(f"Description: {call.get('Description', '')}\n")
                    file.write(f"Resolved: {'Yes' if call.get('ResolutionStatus', False) else 'No'}\n")
                    if call.get('ResolutionStatus', False):
                        file.write(f"Resolved By: {call.get('ResolvedBy', '')}\n")
                        file.write(f"Resolved At: {call.get('ResolutionTimestamp', '')}\n")
                    file.write(f"Red Flag: {'Yes' if call.get('RedFlag', False) else 'No'}\n")
                    file.write(f"Report Number: {call.get('ReportNumber', '')}\n")
                    file.write("="*40 + "\n")
            self.log(f"Report saved to {filename}")
            self.status_var.set(f"Report saved: {filename}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_data(self):
        """Save data to a file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".bin",
            filetypes=[("Binary", "*.bin"), ("Text", "*.txt"),
                       ("CSV", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        filetype = filename.split('.')[-1]
        try:
            self.manager.save_to_file(filename, filetype)
            self.log(f"Data saved to {filename}")
            self.status_var.set(f"Data saved: {filename}")
            self.has_unsaved_changes = False
            self.last_file_mtime = get_file_modification_time(filename)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_data(self):
        """Load data from a file."""
        filename = filedialog.askopenfilename(
            filetypes=[("Binary", "*.bin"), ("Text", "*.txt"),
                       ("CSV", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        filetype = filename.split('.')[-1]
        try:
            loaded = self.manager.load_from_file(filename, filetype)
            if not loaded:
                messagebox.showwarning("Load Warning", "File not found or could not be loaded.")
                return
            self.update_table()
            self.log(f"Data loaded from {filename}")
            self.status_var.set(f"Data loaded: {filename}")
            self.has_unsaved_changes = False
            self.last_file_mtime = get_file_modification_time(filename)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def change_user(self):
        """Change the current user."""
        new_user = simpledialog.askstring("Change User", "Enter new username:")
        if not new_user or not new_user.strip():
            messagebox.showwarning("Invalid Input", "Username cannot be empty.")
            return
        self.manager.set_user(new_user.strip())
        self.status_var.set(f"User changed to: {new_user.strip()}")
        self.log(f"User changed to: {new_user.strip()}")

    def show_user_guide(self):
        """Show the user guide."""
        guide = tk.Toplevel(self.root)
        guide.title("User Guide")
        instructions = (
            "1. Enter your username when prompted.\n"
            "2. Fill in the call details and click 'Add Call' to save a new call.\n"
            "3. Select a call from the table to modify, resolve, delete, or restore.\n"
            "4. Use 'Red Flag' to toggle the red-flag status.\n"
            "5. Use 'Show Deleted' to toggle visibility of deleted calls.\n"
            "6. Use 'Search' to filter calls by ID, Caller, or Description.\n"
            "7. Click 'Print Report' to export a text report.\n"
            "8. Your data is autosaved and backed up every 15 minutes."
        )
        tk.Label(guide, text=instructions, justify="left", padx=10, pady=10).pack()

    def update_table(self, filter_text=None):
        """Update the table with current call data."""
        for row in self.table.get_children():
            self.table.delete(row)

        calls_to_show = (
            [c for c in self.manager.calls if not c.get("Deleted", False)]
            if not self.show_deleted else self.manager.calls.copy()
        )
        if filter_text:
            filter_lower = filter_text.lower()
            calls_to_show = [
                c for c in calls_to_show
                if filter_lower in c.get("CallID", "").lower()
                or filter_lower in c.get("Caller", "").lower()
                or filter_lower in c.get("Description", "").lower()
                or filter_lower in c.get("Location", "").lower()
                or filter_lower in c.get("Code", "").lower()
            ]

        for call in calls_to_show:
            tags = []
            if call.get("ResolutionStatus", False):
                tags.append("resolved")
            if call.get("RedFlag", False):
                tags.append("redflag")
            if call.get("Deleted", False):
                tags.append("deleted")
            values = [
                call.get("CallID", ""),
                call.get("CallDate", ""),
                call.get("CallTime", ""),
                call.get("ResolutionTimestamp", ""),
                call.get("ResolutionStatus", False),
                call.get("InputMedium", ""),
                call.get("Source", ""),
                call.get("Caller", ""),
                call.get("Location", ""),
                call.get("Code", ""),
                call.get("Description", ""),
                call.get("ResolvedBy", ""),
                call.get("CreatedBy", ""),
                call.get("ModifiedBy", ""),
                call.get("ReportNumber", "")
            ]
            self.table.insert("", tk.END, values=values, tags=tags)
        if calls_to_show:
            self.table.see(self.table.get_children()[-1])

    def on_search(self):
        """Handle search functionality."""
        filter_text = self.search_var.get().strip()
        self.update_table(filter_text)

    def load_autosave(self):
        """Attempt to load autosave.bin (or fallback to autosave.txt)."""
        loaded = False
        if os.path.exists("autosave.bin"):
            try:
                loaded = self.manager.load_from_file("autosave.bin", "bin")
                self.last_loaded_hash = self.manager._calculate_hash()
                self.log("Autosave loaded from binary.")
                self.update_table()
                self.last_file_mtime = get_file_modification_time("autosave.bin")
            except Exception as e:
                self.log(f"Failed to load binary autosave: {e}")
        if not loaded and os.path.exists("autosave.txt"):
            try:
                loaded = self.manager.load_from_file("autosave.txt", "txt")
                self.last_loaded_hash = self.manager._calculate_hash()
                self.log("Autosave loaded from text.")
                self.update_table()
                # Immediately write back to binary for future
                self.manager.save_to_file("autosave.bin", "bin")
                self.last_file_mtime = get_file_modification_time("autosave.bin")
            except Exception as e:
                self.log(f"Failed to load text autosave: {e}")
        if not loaded:
            self.log("No autosave found, starting fresh.")

    def start_backup_timer(self):
        """Start the periodic backup timer."""
        timer = Timer(900, self.create_backup)  # every 15 minutes
        timer.daemon = True
        timer.start()

    def create_backup(self):
        """Create a backup of the current data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        prefix = f"BackUp{self.backup_counter}_{timestamp}"
        filename = os.path.join(backup_dir, f"{prefix}.bin")
        try:
            self.manager.save_to_file(filename, "bin")
            self.log(f"Backup created: {prefix}")
        except Exception as e:
            self.log(f"Failed to create backup: {e}")
        self.backup_counter += 1
        self.rotate_backups(backup_dir)
        self.start_backup_timer()

    def rotate_backups(self, backup_dir):
        """Rotate old backups to maintain max_backups limit."""
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.startswith("BackUp") and f.endswith(".bin")
        ]
        backup_files.sort(
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f))
        )
        while len(backup_files) > self.max_backups:
            oldest = backup_files.pop(0)
            try:
                os.remove(os.path.join(backup_dir, oldest))
                self.log(f"Rotated out old backup: {oldest}")
            except Exception as e:
                self.log(f"Error removing old backup {oldest}: {e}")

    def start_autosave_watcher(self):
        """Start watching for autosave file changes."""
        if not self.watching_autosave:
            self.watching_autosave = True
            self.watcher_thread = Thread(target=self.watch_autosave_changes, daemon=True)
            self.watcher_thread.start()

    def watch_autosave_changes(self):
        """Monitor autosave file for external changes."""
        while self.watching_autosave:
            try:
                current_mtime = get_file_modification_time(self.autosave_file)
                if current_mtime > self.last_file_mtime and self.last_file_mtime != 0:
                    self.last_file_mtime = current_mtime
                    self.root.after(0, self.handle_external_changes)
                
                if self.last_file_mtime == 0 and os.path.exists(self.autosave_file):
                    self.last_file_mtime = get_file_modification_time(self.autosave_file)
                
                time.sleep(2)  # Check every 2 seconds
            except Exception as e:
                self.log(f"Autosave watcher error: {str(e)}")
                time.sleep(5)

    def handle_external_changes(self):
        """Handle detected changes in the autosave file."""
        if messagebox.askyesno(
            "External Changes Detected",
            "The autosave file has been modified externally. Reload data?",
            parent=self.root
        ):
            self.load_autosave()
            self.log("Data reloaded due to external changes in autosave.bin")
            self.status_var.set("Data reloaded from external changes")

    def on_close(self):
        """Clean up before closing."""
        self.watching_autosave = False
        if hasattr(self, 'watcher_thread') and self.watcher_thread.is_alive():
            self.watcher_thread.join(timeout=1)
        
        has_pending_call = (
            self.caller_var.get().strip()
            or self.description_entry.get("1.0", tk.END).strip()
            or self.location_var.get().strip()
        )
        
        if self.has_unsaved_changes or has_pending_call:
            response = messagebox.askyesnocancel(
                "Save Changes",
                "You have unsaved changes or a pending call entry. Save before exiting?",
                detail=(
                    "Click 'Yes' to save and exit, 'No' to exit without saving, "
                    "or 'Cancel' to return."
                )
            )
            if response is None:
                return
            elif response:
                if has_pending_call:
                    self.add_call()
                self.save_and_reload()
        self.root.destroy()