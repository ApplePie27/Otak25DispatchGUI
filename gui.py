import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from dispatch_call_manager import DispatchCallManager
from utils import calculate_file_hash
from datetime import datetime
import shutil
import os
from threading import Timer

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

        # Create all UI components first
        self.create_log_area()
        self.create_table()
        
        # Then load data
        self.load_autosave()
        self.login()

        # Input Fields
        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar(value="A")
        self.code_var = tk.StringVar(value="Green")
        self.description_var = tk.StringVar()

        # Resolution Fields
        self.resolution_status_var = tk.BooleanVar(value=False)
        self.resolved_by_var = tk.StringVar()

        # GUI Layout
        self.create_menu_bar()
        self.create_input_fields()
        self.create_buttons()
        self.create_search_bar()
        self.create_status_bar()

        self.configure_grid_weights()
        self.root.after(125, self.reload_data_loop)
        self.start_backup_timer()

    def start_backup_timer(self):
        """Initialize and start the backup timer."""
        self.backup_timer = Timer(900, self.create_backup)  # 15 minutes = 900 seconds
        self.backup_timer.daemon = True
        self.backup_timer.start()
        self.log("Backup timer started")

    def create_backup(self):
        """Create timestamped backup files."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_prefix = f"BackUp{self.backup_counter}_{timestamp}"
            txt_backup = os.path.join(backup_dir, f"{backup_prefix}.txt")
            csv_backup = os.path.join(backup_dir, f"{backup_prefix}.csv")
            
            # Create backup copies
            shutil.copy2("autosave.txt", txt_backup)
            if os.path.exists("autosave.csv"):
                shutil.copy2("autosave.csv", csv_backup)
            
            self.log(f"Backup created: {backup_prefix}")
            self.backup_counter += 1
            
            # Rotate old backups
            self.rotate_backups(backup_dir)
            
        except Exception as e:
            self.log(f"Backup failed: {e}")
        finally:
            # Restart the timer
            self.start_backup_timer()

    def rotate_backups(self, backup_dir):
        """Keep only the most recent backups."""
        try:
            backup_files = []
            for f in os.listdir(backup_dir):
                if f.startswith("BackUp") and (f.endswith(".txt") or f.endswith(".csv")):
                    backup_files.append(os.path.join(backup_dir, f))
            
            # Sort by modification time (oldest first)
            backup_files.sort(key=lambda x: os.path.getmtime(x))
            
            # Delete oldest if we exceed max_backups
            while len(backup_files) > self.max_backups * 2:  # *2 for txt and csv
                os.remove(backup_files[0])
                backup_files.pop(0)
                self.log(f"Rotated out old backup: {os.path.basename(backup_files[0])}")
                
        except Exception as e:
            self.log(f"Backup rotation failed: {e}")

    # ... [All other methods remain exactly the same as in the previous complete implementation]
    # Make sure to include ALL methods from the previous complete version

    def create_log_area(self):
        """Create the log area for system messages."""
        self.log_area = scrolledtext.ScrolledText(self.root, width=80, height=10)
        self.log_area.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")
        self.log_area.config(state=tk.DISABLED)

    def log(self, message):
        """Log a message to the log area."""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.see(tk.END)

    def configure_grid_weights(self):
        """Configure grid weights to make the UI resizable."""
        self.root.grid_rowconfigure(2, weight=1)  # Table row
        self.root.grid_rowconfigure(4, weight=1)  # Log area row
        self.root.grid_columnconfigure(0, weight=1)  # Single column

    def create_menu_bar(self):
        """Create a menu bar for the application."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save", command=self.save_data)
        file_menu.add_command(label="Load", command=self.load_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        menubar.add_cascade(label="Help", menu=help_menu)

    def save_data(self):
        """Save data to a file."""
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            try:
                self.manager.save_to_file(filename, filetype)
                self.log(f"Data saved to {filename}")
                self.update_status("Data saved successfully.")
            except Exception as e:
                self.log(f"Failed to save data: {e}")
                self.update_status(f"Failed to save data: {e}")
                messagebox.showerror("Error", f"Failed to save data: {e}")

    def load_data(self):
        """Load data from a file."""
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            try:
                if self.manager.load_from_file(filename, filetype):
                    self.update_table()
                    self.log(f"Data loaded from {filename}")
                    self.update_status("Data loaded successfully.")
                else:
                    self.log(f"Failed to load data from {filename}")
                    self.update_status("Failed to load data.")
            except Exception as e:
                self.log(f"Error loading data: {e}")
                self.update_status(f"Error loading data: {e}")
                messagebox.showerror("Error", f"Error loading data: {e}")

    def show_user_guide(self):
        """Display a user guide in a new window."""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("User Guide")
        guide_text = scrolledtext.ScrolledText(guide_window, width=80, height=25)
        guide_text.insert(tk.END, "Dispatch Call Management System User Guide\n\n"
                              "Adding a New Call\n"
                              " 1. Fill in the input fields (Caller, Description, etc.).\n"
                              " 2. Click 'Add Call' to save the call.\n\n"
                              "Resolving a Call\n"
                              " 1. Select a call from the table.\n"
                              " 2. Click 'Resolve Call' and enter the resolver's name.\n\n"
                              "Modifying a Call\n"
                              " 1. Select a call from the table.\n"
                              " 2. Update the input fields.\n"
                              " 3. Click 'Modify Call'.\n\n"
                              "Deleting a Call\n"
                              " 1. Select a call from the table.\n"
                              " 2. Click 'Delete Call' (marks as deleted).\n\n"
                              "Viewing Deleted Calls\n"
                              " 1. Click 'Show Deleted' to toggle visibility.\n"
                              " 2. Select a deleted call and click 'Restore' to undelete.\n\n"
                              "Backup System\n"
                              " - Automatic backups created every 15 minutes\n"
                              " - Stored in 'backups' folder\n"
                              " - Keeps last 10 backups\n")
        guide_text.config(state=tk.DISABLED)
        guide_text.pack(padx=10, pady=10)

    def create_status_bar(self):
        """Create a status bar at the bottom of the window."""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, sticky="ew")

    def update_status(self, message):
        """Update the status bar with a message."""
        self.status_var.set(message)

    def load_autosave(self):
        """Load data from the autosave file."""
        try:
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = self.manager._calculate_hash()
                self.log("Autosave loaded successfully.")
                self.update_table()
            else:
                self.log("No autosave found, starting with empty data.")
                self.manager.calls = []
                self.manager.report_counter = 1
                self.last_loaded_hash = self.manager._calculate_hash()
        except Exception as e:
            self.log(f"Error loading autosave: {e}")
            messagebox.showerror("Error", f"Error loading autosave: {e}")

    def login(self):
        """Prompt the user to log in."""
        username = simpledialog.askstring("Login", "Enter your username:", parent=self.root)
        if username:
            self.manager.set_user(username)
            self.log(f"User '{username}' logged in.")
        else:
            self.root.destroy()

    def create_input_fields(self):
        """Create input fields for new dispatch calls."""
        fields_frame = ttk.LabelFrame(self.root, text="New Dispatch Call")
        fields_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Input Medium dropdown
        ttk.Label(fields_frame, text="Input Medium:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        input_medium_options = ["Radio", "Social Media"]
        input_medium_dropdown = ttk.Combobox(fields_frame, textvariable=self.input_medium_var, values=input_medium_options)
        input_medium_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        input_medium_dropdown.bind("<<ComboboxSelected>>", self.update_source_and_location_options)

        # Source dropdown
        ttk.Label(fields_frame, text="Source:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.source_dropdown = ttk.Combobox(fields_frame, textvariable=self.source_var)
        self.source_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Caller entry
        ttk.Label(fields_frame, text="Caller:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(fields_frame, textvariable=self.caller_var).grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Location dropdown
        ttk.Label(fields_frame, text="Location:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.location_dropdown = ttk.Combobox(fields_frame, textvariable=self.location_var)
        self.location_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        # Code dropdown
        ttk.Label(fields_frame, text="Code:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        code_options = ["Signal 13", "Green", "Orange", "Red", "Blue", "Yellow", "Yellow M", "Purple", "Silver", "Adam", "Black"]
        ttk.Combobox(fields_frame, textvariable=self.code_var, values=code_options).grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        # Description text area
        ttk.Label(fields_frame, text="Description:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, width=40, height=5)
        self.description_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        # Resolution Checkbox and Resolver Name Entry
        ttk.Checkbutton(
            fields_frame,
            text=" ",
            variable=self.resolution_status_var,
            command=self.toggle_resolver_entry
        ).grid(row=6, column=0, padx=(5, 20), pady=5, sticky="w")

        self.resolver_entry = ttk.Entry(fields_frame, textvariable=self.resolved_by_var, state=tk.DISABLED)
        self.resolver_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(fields_frame, text="Resolved By:").grid(row=6, column=0, padx=0, pady=5, sticky="e")

        self.update_source_and_location_options()

    def toggle_resolver_entry(self):
        """Enable or disable the resolver entry based on the checkbox state."""
        if self.resolution_status_var.get():
            self.resolver_entry.config(state=tk.NORMAL)
        else:
            self.resolver_entry.config(state=tk.DISABLED)
            self.resolved_by_var.set("")

    def update_source_and_location_options(self, event=None):
        """Update source and location options based on the selected input medium."""
        input_medium = self.input_medium_var.get()
        if input_medium == "Radio":
            self.source_dropdown["values"] = ["Safety", "General", "First Aid"]
            self.location_dropdown["values"] = ["A", "B", "C", "D", "E", "F", "G"]
        elif input_medium == "Social Media":
            self.source_dropdown["values"] = ["Discord", "Phone Call", "SMS"]
            self.location_dropdown["values"] = ["H", "I", "J", "K", "L", "M", "N"]

        self.source_var.set(self.source_dropdown["values"][0] if self.source_dropdown["values"] else "")
        self.location_var.set(self.location_dropdown["values"][0] if self.location_dropdown["values"] else "")

    def create_buttons(self):
        """Create buttons for managing calls."""
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.search_label_click_count = 0

        ttk.Button(buttons_frame, text="Add Call", command=self.add_call).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Modify Call", command=self.modify_call).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Resolve Call", command=self.resolve_call).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Red Flag", command=self.red_flag_call).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_input_fields).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Delete Call", command=self.delete_call).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Restore", command=self.restore_call).grid(row=0, column=8, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Show Deleted", command=self.toggle_deleted).grid(row=0, column=7, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Print Report", command=self.print_report).grid(row=0, column=5, padx=5, pady=5)
        
    def clear_input_fields(self):
        """Clear all input fields."""
        self.caller_var.set("")
        self.description_entry.delete("1.0", tk.END)
        self.resolution_status_var.set(False)
        self.resolved_by_var.set("")
        self.resolver_entry.config(state=tk.DISABLED)
        self.update_status("Input fields cleared.")

    def create_table(self):
        """Create the table to display calls."""
        self.table = ttk.Treeview(
            self.root,
            columns=(
                "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                "InputMedium", "Source", "Caller", "Location", "Code", "Description", "ResolvedBy",
                "CreatedBy", "ModifiedBy", "ReportNumber"
            ),
            show="headings"
        )
        self.table.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        # Define column headings
        columns = [
            ("CallID", "Call ID"),
            ("CallDate", "Call Date"),
            ("CallTime", "Call Time"),
            ("ResolutionTimestamp", "Resolution Timestamp"),
            ("ResolutionStatus", "Resolution Status"),
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
        for col, heading in columns:
            self.table.heading(col, text=heading)
            if col == "Description":
                self.table.column(col, width=120, anchor="w")
            else:
                self.table.column(col, width=120, anchor="center")

        self.table.bind("<<TreeviewSelect>>", self.load_selected_call)
        self.update_table()

    def load_selected_call(self, event):
        """Load the selected call's details into the input fields."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            for call in self.manager.calls:
                if call["CallID"] == call_id:
                    self.input_medium_var.set(call.get("InputMedium", ""))
                    self.source_var.set(call.get("Source", ""))
                    self.caller_var.set(call.get("Caller", ""))
                    self.location_var.set(call.get("Location", ""))
                    self.code_var.set(call.get("Code", ""))
                    self.description_entry.delete("1.0", tk.END)
                    self.description_entry.insert(tk.END, call.get("Description", ""))
                    self.resolution_status_var.set(call.get("ResolutionStatus", False))
                    self.resolved_by_var.set(call.get("ResolvedBy", ""))
                    self.toggle_resolver_entry()
                    break

    def update_table(self, filter_text=None):
        """Update the table with the latest calls."""
        for row in self.table.get_children():
            self.table.delete(row)

        filtered_calls = [call for call in self.manager.calls 
                         if not call.get("Deleted", False) or self.show_deleted]
        
        if filter_text:
            filtered_calls = [
                call for call in filtered_calls
                if filter_text.lower() in call["CallID"].lower() or
                filter_text.lower() in call["Caller"].lower() or
                filter_text.lower() in call["Description"].lower()
            ]

        for call in filtered_calls:
            resolved = call.get("ResolutionStatus", False)
            red_flag = call.get("RedFlag", False)
            deleted = call.get("Deleted", False)
            
            tags = []
            if resolved:
                tags.append("resolved")
            if red_flag:
                tags.append("redflag")
            if deleted:
                tags.append("deleted")
                
            self.table.insert("", "end", values=(
                call["CallID"],
                call["CallDate"],
                call["CallTime"],
                call.get("ResolutionTimestamp", ""),
                "Resolved" if resolved else "Unresolved",
                call.get("InputMedium", ""),
                call["Source"],
                call["Caller"],
                call["Location"],
                call["Code"],
                call["Description"],
                call.get("ResolvedBy", ""),
                call.get("CreatedBy", ""),
                call.get("ModifiedBy", ""),
                call.get("ReportNumber", "")
            ), tags=tuple(tags))

        self.table.tag_configure("resolved", background="light green")
        self.table.tag_configure("redflag", background="light coral")
        self.table.tag_configure("deleted", background="light gray", foreground="gray")

        if self.table.get_children():
            self.table.see(self.table.get_children()[-1])

    def save_and_reload(self):
        """Save the data and reload it."""
        try:
            self.manager.save_to_file("autosave.txt", filetype="txt")
            self.manager.save_to_file("autosave.csv", filetype="csv")
            self.log("Autosave completed (both txt and csv).")
            
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.update_table()
                self.log("Data reloaded successfully from autosave.txt.")
            else:
                self.log("Failed to reload data from autosave.txt.")
        except Exception as e:
            self.log(f"Error during save/reload: {e}")
            messagebox.showerror("Autosave Error", f"Error during autosave: {e}")

    def reload_data_loop(self):
        """Reload data from the autosave file if it has changed."""
        current_hash = calculate_file_hash("autosave.txt")
        if current_hash != self.last_loaded_hash:
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = current_hash
                self.update_table()
                self.log("Data reloaded due to changes in autosave file.")

        self.root.after(125, self.reload_data_loop)

    def add_call(self):
        """Add a new call."""
        caller = self.caller_var.get().strip()
        description = self.description_entry.get("1.0", tk.END).strip()

        if not caller:
            messagebox.showwarning("Input Error", "Caller field cannot be empty.")
            return
        if not description:
            messagebox.showwarning("Input Error", "Description field cannot be empty.")
            return

        call = {
            "InputMedium": self.input_medium_var.get(),
            "Source": self.source_var.get(),
            "Caller": caller,
            "Location": self.location_var.get(),
            "Code": self.code_var.get(),
            "Description": description,
            "ResolutionStatus": self.resolution_status_var.get(),
            "ResolvedBy": self.resolved_by_var.get() if self.resolution_status_var.get() else ""
        }
        self.manager.add_call(call)
        self.save_and_reload()
        self.log(f"Call added: {call['CallID']}")
        self.update_status("Call added successfully.")

    def resolve_call(self):
        """Resolve a call."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            resolved_by = simpledialog.askstring("Resolve Call", "Enter the name who resolved the call:", parent=self.root)
            if resolved_by:
                self.manager.resolve_call(call_id, resolved_by)
                self.save_and_reload()
                self.log(f"Call resolved: {call_id} by {resolved_by}")
                self.update_status("Call resolved successfully.")

    def modify_call(self):
        """Modify an existing call."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            updated_call = {
                "InputMedium": self.input_medium_var.get(),
                "Source": self.source_var.get(),
                "Caller": self.caller_var.get(),
                "Location": self.location_var.get(),
                "Code": self.code_var.get(),
                "Description": self.description_entry.get("1.0", tk.END).strip(),
                "ResolutionStatus": self.resolution_status_var.get(),
                "ResolvedBy": self.resolved_by_var.get() if self.resolution_status_var.get() else ""
            }
            self.manager.modify_call(call_id, updated_call)
            self.save_and_reload()
            self.log(f"Call modified: {call_id}")
            self.update_status("Call modified successfully.")

    def delete_call(self):
        """Mark the selected call as deleted."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                f"Are you sure you want to mark call {call_id} as deleted?"
            )
            
            if confirm:
                self.manager.delete_call(call_id)
                self.save_and_reload()
                self.log(f"Call marked as deleted: {call_id}")
                self.update_status("Call marked as deleted.")

    def restore_call(self):
        """Restore a deleted call."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            self.manager.restore_call(call_id)
            self.save_and_reload()
            self.log(f"Call restored: {call_id}")
            self.update_status("Call restored successfully.")

    def print_report(self):
        """Generate and print a report of all calls."""
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if filename:
            include_deleted = messagebox.askyesno("Include Deleted", "Include deleted calls in the report?")
            
            with open(filename, "w") as file:
                file.write("Dispatch Call Report\n")
                file.write("=" * 50 + "\n")
                for call in self.manager.calls:
                    if not include_deleted and call.get("Deleted", False):
                        continue
                        
                    file.write(f"Call ID: {call['CallID']}\n")
                    file.write(f"Status: {'Deleted' if call.get('Deleted') else 'Active'}\n")
                    file.write(f"Caller: {call['Caller']}\n")
                    file.write(f"Description: {call['Description']}\n")
                    file.write(f"Resolution: {'Resolved' if call.get('ResolutionStatus') else 'Unresolved'}\n")
                    file.write(f"Red Flag: {'Yes' if call.get('RedFlag') else 'No'}\n")
                    file.write(f"Report Number: {call.get('ReportNumber', 'N/A')}\n")
                    file.write("=" * 50 + "\n")
                    
            self.log(f"Report saved to {filename}")
            self.update_status("Report generated successfully.")

    def create_search_bar(self):
        """Create the search bar."""
        search_frame = ttk.Frame(self.root)
        search_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")

        self.search_label_click_count = 0

        self.search_label = ttk.Label(search_frame, text="Search:")
        self.search_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.search_label.bind("<Button-1>", self.on_search_label_click)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        search_entry.bind("<KeyRelease>", self.on_search)

    def on_search_label_click(self, event):
        """Handle clicks on the search label."""
        self.search_label_click_count += 1
        if self.search_label_click_count == 5:
            messagebox.showinfo("Hidden Cheesecake", "Oh no, you have found the hidden cheesecake - Nhpha")
            self.search_label_click_count = 0

    def on_search(self, event=None):
        """Handle search functionality."""
        filter_text = self.search_var.get()
        self.update_table(filter_text=filter_text)

    def red_flag_call(self):
        """Toggle the red flag status of the selected call."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            self.manager.red_flag_call(call_id)
            self.save_and_reload()
            self.log(f"Call red-flag toggled: {call_id}")
            self.update_status("Call red-flag status updated.")

    def toggle_deleted(self):
        """Toggle display of deleted calls."""
        self.show_deleted = not self.show_deleted
        self.update_table()
        self.update_status(f"Showing {'all' if self.show_deleted else 'active'} calls.")