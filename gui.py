import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from dispatch_call_manager import DispatchCallManager
from utils import calculate_file_hash
from datetime import datetime
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
        self.has_unsaved_changes = False
        self.last_call_entered = None

        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.level_var = tk.StringVar(value="1")
        self.emplacement_var = tk.StringVar()
        self.code_var = tk.StringVar(value="Green")
        self.description_var = tk.StringVar()
        self.resolution_status_var = tk.BooleanVar(value=False)
        self.resolved_by_var = tk.StringVar()

        self.code_descriptions = {
            "Signal 13": "Signal 13: Immediate personnel in danger.",
            "Green": "Green: Supervisor backup.",
            "Orange": "Orange: Hazardous material.",
            "Red": "Red: Suspected fire.",
            "Blue": "Blue: Life threatening medical emergency.",
            "Yellow": "Yellow: Attendee unable to walk due to minor medical issue.",
            "Yellow M": "Yellow M: Mental health crisis.",
            "Purple": "Purple: Harassment, unwanted attention, or contact.",
            "Silver": "Silver: Active assailant.",
            "Adam": "Adam: Lost child.",
            "Black": "Black: Suspicious package or call threat.",
        }
        self.code_description_var = tk.StringVar(value=self.code_descriptions[self.code_var.get()])

        self.emplacement_options_by_level = {
            "1": ["Registration", "Oasis"],
            "Entrance": ["Riopelle", "Metro", "Viger", "Oasis"],
            "2": ["Exhibition", "Autograph", "Event"],
            "5": ["Presentation", "Dance", "Tabletop", "Presentation", "Gameshow", "Craft zone", "Model expo", "Overflow", "Tech op", "Panel", "Video"],
            "7": ["Terrace", "Cosplay cafe", "Workshop", "Presentation"]
        }

        self.create_status_bar()
        self.create_log_area()
        if not self.ensure_user_logged_in():
            self.root.destroy()
            return
        self.create_table()
        self.load_autosave()
        self.create_menu_bar()
        self.create_input_fields()
        self.create_buttons()
        self.create_search_bar()
        self.configure_grid_weights()
        self.root.after(125, self.reload_data_loop)
        self.start_backup_timer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, sticky="ew")

    def create_log_area(self):
        self.log_area = scrolledtext.ScrolledText(self.root, width=80, height=10)
        self.log_area.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")
        self.log_area.config(state=tk.DISABLED)

    def log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.see(tk.END)

    def ensure_user_logged_in(self):
        while not self.manager.current_user:
            username = simpledialog.askstring("Login", "Enter your username:", parent=self.root)
            if username:
                self.manager.set_user(username)
                self.update_status(f"User '{username}' logged in")
                return True
            else:
                if messagebox.askyesno("Exit", "No username entered. Exit application?"):
                    return False
        return True

    def update_status(self, message):
        self.status_var.set(message)

    def create_menu_bar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save", command=self.save_data)
        file_menu.add_command(label="Load", command=self.load_data)
        file_menu.add_separator()
        file_menu.add_command(label="Change User", command=self.change_user)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        menubar.add_cascade(label="Help", menu=help_menu)

    def create_input_fields(self):
        fields_frame = ttk.LabelFrame(self.root, text="New Dispatch Call")
        fields_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(fields_frame, text="Input Medium:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        input_medium_options = ["Radio", "Social Media"]
        input_medium_dropdown = ttk.Combobox(fields_frame, textvariable=self.input_medium_var, values=input_medium_options)
        input_medium_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        input_medium_dropdown.bind("<<ComboboxSelected>>", self.update_source_and_level_options)

        ttk.Label(fields_frame, text="Source:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.source_dropdown = ttk.Combobox(fields_frame, textvariable=self.source_var)
        self.source_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(fields_frame, text="Caller ID:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(fields_frame, textvariable=self.caller_var).grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Level & Emplacement row
        ttk.Label(fields_frame, text="Level:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        level_options = ["1", "Entrance", "2", "5", "7"]
        self.level_dropdown = ttk.Combobox(fields_frame, textvariable=self.level_var, values=level_options, state="readonly")
        self.level_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        self.level_dropdown.bind("<<ComboboxSelected>>", self.update_emplacement_options)

        ttk.Label(fields_frame, text="Emplacement:").grid(row=3, column=2, padx=5, pady=5, sticky="w")
        self.emplacement_dropdown = ttk.Combobox(fields_frame, textvariable=self.emplacement_var, state="readonly")
        self.emplacement_dropdown.grid(row=3, column=3, padx=5, pady=5, sticky="ew")

        # Code row
        ttk.Label(fields_frame, text="Code:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        code_options = ["Signal 13", "Green", "Orange", "Red", "Blue", "Yellow", "Yellow M", "Purple", "Silver", "Adam", "Black"]
        code_dropdown = ttk.Combobox(fields_frame, textvariable=self.code_var, values=code_options, state="readonly")
        code_dropdown.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        code_dropdown.bind("<<ComboboxSelected>>", self.update_code_description)

        # Code Description (separate row, spanning all columns)
        self.code_description_label = ttk.Label(
            fields_frame,
            textvariable=self.code_description_var,
            wraplength=350,
            foreground="dimgray"
        )
        self.code_description_label.grid(row=5, column=1, padx=5, pady=(0, 10), sticky="w")

        # Description text area
        ttk.Label(fields_frame, text="Description:").grid(row=6, column=0, padx=5, pady=5, sticky="nw")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, width=40, height=5)
        self.description_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")

        # Resolution Checkbox and Resolver Name Entry
        ttk.Checkbutton(
            fields_frame,
            text=" ",
            variable=self.resolution_status_var,
            command=self.toggle_resolver_entry
        ).grid(row=7, column=0, padx=(5, 20), pady=5, sticky="w")

        self.resolver_entry = ttk.Entry(fields_frame, textvariable=self.resolved_by_var, state=tk.DISABLED)
        self.resolver_entry.grid(row=7, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(fields_frame, text="Resolved By:").grid(row=7, column=0, padx=0, pady=5, sticky="e")

        self.update_source_and_level_options()
        self.update_code_description()
        self.update_emplacement_options()

    def create_buttons(self):
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        ttk.Button(buttons_frame, text="Add Call", command=self.add_call).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Save Modification", command=self.modify_call).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Resolve Call", command=self.resolve_call).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Red Flag", command=self.red_flag_call).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_input_fields).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Delete Call", command=self.delete_call).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Restore", command=self.restore_call).grid(row=0, column=8, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Show Deleted", command=self.toggle_deleted).grid(row=0, column=7, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Print Report", command=self.print_report).grid(row=0, column=5, padx=5, pady=5)

    def clear_input_fields(self):
        self.caller_var.set("")
        self.description_entry.delete("1.0", tk.END)
        self.resolution_status_var.set(False)
        self.resolved_by_var.set("")
        self.resolver_entry.config(state=tk.DISABLED)
        self.update_status("Input fields cleared.")
        self.update_emplacement_options()

    def configure_grid_weights(self):
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def update_code_description(self, event=None):
        desc = self.code_descriptions.get(self.code_var.get(), "No description available.")
        self.code_description_var.set(desc)

    def update_source_and_level_options(self, event=None):
        input_medium = self.input_medium_var.get()
        if input_medium == "Radio":
            self.source_dropdown["values"] = ["Safety", "General", "First Aid"]
        elif input_medium == "Social Media":
            self.source_dropdown["values"] = ["Discord", "Phone Call", "SMS"]
        self.source_var.set(self.source_dropdown["values"][0] if self.source_dropdown["values"] else "")
        level_options = ["1", "Entrance", "2", "5", "7"]
        self.level_dropdown["values"] = level_options
        self.level_var.set(level_options[0])
        self.update_emplacement_options()

    def update_emplacement_options(self, event=None):
        level = self.level_var.get()
        options = self.emplacement_options_by_level.get(level, [])
        self.emplacement_dropdown["values"] = options
        if options:
            self.emplacement_var.set(options[0])
        else:
            self.emplacement_var.set("")

    def toggle_resolver_entry(self):
        if self.resolution_status_var.get():
            self.resolver_entry.config(state=tk.NORMAL)
        else:
            self.resolver_entry.config(state=tk.DISABLED)
            self.resolved_by_var.set("")

    def create_table(self):
        self.table = ttk.Treeview(
            self.root,
            columns=(
                "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                "InputMedium", "Source", "Caller", "Level", "Emplacement", "Code", "Description", "ResolvedBy",
                "CreatedBy", "ModifiedBy", "ReportNumber"
            ),
            show="headings"
        )
        self.table.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        columns = [
            ("CallID", "Call ID"),
            ("CallDate", "Call Date"),
            ("CallTime", "Call Time"),
            ("ResolutionTimestamp", "Resolution Timestamp"),
            ("ResolutionStatus", "Resolution Status"),
            ("InputMedium", "Input Medium"),
            ("Source", "Source"),
            ("Caller", "Caller"),
            ("Level", "Level"),
            ("Emplacement", "Emplacement"),
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

    def update_table(self, filter_text=None):
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
                call["Level"],
                call.get("Emplacement", ""),
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

    def load_selected_call(self, event):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            for call in self.manager.calls:
                if call["CallID"] == call_id:
                    self.input_medium_var.set(call.get("InputMedium", ""))
                    self.source_var.set(call.get("Source", ""))
                    self.caller_var.set(call.get("Caller", ""))
                    self.level_var.set(call.get("Level", ""))
                    self.update_emplacement_options()
                    self.emplacement_var.set(call.get("Emplacement", ""))
                    self.code_var.set(call.get("Code", ""))
                    self.description_entry.delete("1.0", tk.END)
                    self.description_entry.insert(tk.END, call.get("Description", ""))
                    self.resolution_status_var.set(call.get("ResolutionStatus", False))
                    self.resolved_by_var.set(call.get("ResolvedBy", ""))
                    self.toggle_resolver_entry()
                    self.update_code_description()
                    break

    def add_call(self):
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
            "Level": self.level_var.get(),
            "Emplacement": self.emplacement_var.get(),
            "Code": self.code_var.get(),
            "Description": description,
            "ResolutionStatus": self.resolution_status_var.get(),
            "ResolvedBy": self.resolved_by_var.get() if self.resolution_status_var.get() else ""
        }
        self.manager.add_call(call)
        self.last_call_entered = call['CallID']
        self.log(f"Call added: {call['CallID']}")
        self.update_status("Call added successfully.")
        self.has_unsaved_changes = True
        self.save_and_reload()
        self.clear_input_fields()

    def modify_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            updated_call = {
                "InputMedium": self.input_medium_var.get(),
                "Source": self.source_var.get(),
                "Caller": self.caller_var.get(),
                "Level": self.level_var.get(),
                "Emplacement": self.emplacement_var.get(),
                "Code": self.code_var.get(),
                "Description": self.description_entry.get("1.0", tk.END).strip(),
                "ResolutionStatus": self.resolution_status_var.get(),
                "ResolvedBy": self.resolved_by_var.get() if self.resolution_status_var.get() else ""
            }
            self.manager.modify_call(call_id, updated_call)
            self.save_and_reload()
            self.log(f"Call modified: {call_id}")
            self.update_status("Call modified successfully.")
            self.has_unsaved_changes = True

    def resolve_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            resolved_by = simpledialog.askstring("Resolve Call", "Enter the name who resolved the call:", parent=self.root)
            if resolved_by:
                self.manager.resolve_call(call_id, resolved_by)
                self.save_and_reload()
                self.log(f"Call resolved: {call_id} by {resolved_by}")
                self.update_status("Call resolved successfully.")
                self.has_unsaved_changes = True

    def delete_call(self):
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
                self.has_unsaved_changes = True

    def restore_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            self.manager.restore_call(call_id)
            self.save_and_reload()
            self.log(f"Call restored: {call_id}")
            self.update_status("Call restored successfully.")
            self.has_unsaved_changes = True

    def print_report(self):
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
                    file.write(f"Level: {call['Level']}\n")
                    file.write(f"Emplacement: {call.get('Emplacement', '')}\n")
                    file.write(f"Resolution: {'Resolved' if call.get('ResolutionStatus') else 'Unresolved'}\n")
                    file.write(f"Red Flag: {'Yes' if call.get('RedFlag') else 'No'}\n")
                    file.write(f"Report Number: {call.get('ReportNumber', 'N/A')}\n")
                    file.write("=" * 50 + "\n")
            self.log(f"Report saved to {filename}")
            self.update_status("Report generated successfully.")

    def create_search_bar(self):
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
        self.search_label_click_count += 1
        if self.search_label_click_count == 5:
            messagebox.showinfo("Hidden Cheesecake", "Oh no, you have found the hidden cheesecake - Nhpha")
            self.search_label_click_count = 0

    def on_search(self, event=None):
        filter_text = self.search_var.get()
        self.update_table(filter_text=filter_text)

    def red_flag_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            self.manager.red_flag_call(call_id)
            self.save_and_reload()
            self.log(f"Call red-flag toggled: {call_id}")
            self.update_status("Call red-flag status updated.")
            self.has_unsaved_changes = True

    def toggle_deleted(self):
        self.show_deleted = not self.show_deleted
        self.update_table()
        self.update_status(f"Showing {'all' if self.show_deleted else 'active'} calls.")

    def start_backup_timer(self):
        self.backup_timer = Timer(900, self.create_backup)
        self.backup_timer.daemon = True
        self.backup_timer.start()
        self.log("Backup timer started")

    def create_backup(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            backup_prefix = f"BackUp{self.backup_counter}_{timestamp}"
            bin_backup = os.path.join(backup_dir, f"{backup_prefix}.bin")
            self.manager.save_to_file(bin_backup, filetype="bin")
            self.log(f"Backup created: {backup_prefix}")
            self.backup_counter += 1
            self.rotate_backups(backup_dir)
        except Exception as e:
            self.log(f"Backup failed: {e}")
        finally:
            self.start_backup_timer()

    def rotate_backups(self, backup_dir):
        try:
            backup_files = []
            for f in os.listdir(backup_dir):
                if f.startswith("BackUp") and f.endswith(".bin"):
                    backup_files.append(os.path.join(backup_dir, f))
            backup_files.sort(key=lambda x: os.path.getmtime(x))
            while len(backup_files) > self.max_backups:
                os.remove(backup_files[0])
                backup_files.pop(0)
                self.log(f"Rotated out old backup: {os.path.basename(backup_files[0])}")
        except Exception as e:
            self.log(f"Backup rotation failed: {e}")

    def save_and_reload(self):
        try:
            self.manager.save_to_file("autosave.bin", filetype="bin")
            self.manager.save_to_file("autosave.txt", filetype="txt")
            self.manager.save_to_file("autosave.csv", filetype="csv")
            self.log("Autosave completed (primary binary format)")
            self.has_unsaved_changes = False
            self.last_call_entered = None
            if self.manager.load_from_file("autosave.bin", filetype="bin"):
                self.update_table()
                self.log("Data reloaded successfully from autosave.bin.")
            else:
                self.log("Failed to reload data from autosave.bin.")
        except Exception as e:
            self.log(f"Error during save/reload: {e}")
            messagebox.showerror("Autosave Error", f"Error during autosave: {e}")

    def reload_data_loop(self):
        current_hash = calculate_file_hash("autosave.bin")
        if current_hash != self.last_loaded_hash:
            if self.manager.load_from_file("autosave.bin", filetype="bin"):
                self.last_loaded_hash = current_hash
                self.update_table()
                self.log("Data reloaded due to changes in autosave file.")
                self.has_unsaved_changes = False
                self.last_call_entered = None
        self.root.after(125, self.reload_data_loop)

    def load_autosave(self):
        try:
            if self.manager.load_from_file("autosave.bin", filetype="bin"):
                self.last_loaded_hash = self.manager._calculate_hash()
                self.log("Autosave loaded successfully from binary file.")
                self.update_table()
            else:
                if self.manager.load_from_file("autosave.txt", filetype="txt"):
                    self.last_loaded_hash = self.manager._calculate_hash()
                    self.log("Autosave loaded from text file (binary not found).")
                    self.update_table()
                    self.manager.save_to_file("autosave.bin", filetype="bin")
                else:
                    self.log("No autosave found, starting with empty data.")
                    self.manager.calls = []
                    self.manager.report_counter = 1
                    self.last_loaded_hash = self.manager._calculate_hash()
        except Exception as e:
            self.log(f"Error loading autosave: {e}")
            messagebox.showerror("Error", f"Error loading autosave: {e}")

    def save_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".bin", 
                                              filetypes=[("Binary Files", "*.bin"), 
                                                         ("Text Files", "*.txt"), 
                                                         ("CSV Files", "*.csv")])
        if filename:
            filetype = "bin" if filename.endswith(".bin") else ("txt" if filename.endswith(".txt") else "csv")
            try:
                self.manager.save_to_file(filename, filetype)
                self.log(f"Data saved to {filename}")
                self.update_status("Data saved successfully.")
                self.has_unsaved_changes = False
                self.last_call_entered = None
            except Exception as e:
                self.log(f"Failed to save data: {e}")
                self.update_status(f"Failed to save data: {e}")
                messagebox.showerror("Error", f"Failed to save data: {e}")

    def load_data(self):
        filename = filedialog.askopenfilename(filetypes=[("Binary Files", "*.bin"),
                                                       ("Text Files", "*.txt"), 
                                                       ("CSV Files", "*.csv")])
        if filename:
            filetype = "bin" if filename.endswith(".bin") else ("txt" if filename.endswith(".txt") else "csv")
            try:
                if self.manager.load_from_file(filename, filetype):
                    self.update_table()
                    self.log(f"Data loaded from {filename}")
                    self.update_status("Data loaded successfully.")
                    self.has_unsaved_changes = False
                    self.last_call_entered = None
                else:
                    self.log(f"Failed to load data from {filename}")
                    self.update_status("Failed to load data.")
            except Exception as e:
                self.log(f"Error loading data: {e}")
                self.update_status(f"Error loading data: {e}")
                messagebox.showerror("Error", f"Error loading data: {e}")

    def change_user(self):
        username = simpledialog.askstring("Change User", "Enter new username:", parent=self.root)
        if username:
            self.manager.set_user(username)
            self.log(f"User changed to '{username}'")
            self.update_status(f"User changed to {username}")

    def show_user_guide(self):
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
                              " 3. Click 'Save Modification'.\n\n"
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

    def on_close(self):
        if not self.manager.current_user:
            if not self.ensure_user_logged_in():
                return
        has_pending_call = (
            self.caller_var.get().strip() or 
            self.description_entry.get("1.0", tk.END).strip()
        )
        if self.has_unsaved_changes or has_pending_call:
            prompt_msg = "You have unsaved changes or an unsubmitted call. Save before exiting?"
            response = messagebox.askyesnocancel(
                "Save Changes",
                prompt_msg,
                detail="Click 'Yes' to save, 'No' to exit without saving, or 'Cancel' to return."
            )
            if response is None:
                return
            elif response:
                if has_pending_call:
                    self.add_call()
                self.save_and_reload()
        self.root.destroy()

# END OF FILE
