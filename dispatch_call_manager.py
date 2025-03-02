import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
import csv
import json
from datetime import datetime
import hashlib
import os


class DispatchCallManager:
    def __init__(self):
        self.calls = []
        self.undo_stack = []
        self.redo_stack = []
        self.report_counter = 1  # Initialize the counter
        self.current_user = None  # Track the current user
        self.last_saved_hash = None  # Track the last saved state

    def set_user(self, username):
        self.current_user = username

    def add_call(self, call):
        call["CallID"] = f"DC25{self.report_counter:04d}"  # Format CallID as DC250001, DC250002, etc.
        self.report_counter += 1  # Increment the counter for the next call
        call["CallDate"] = datetime.now().strftime("%Y-%m-%d")  # Date only
        call["CallTime"] = datetime.now().strftime("%H:%M")  # Time without seconds
        call["ResolutionTimestamp"] = ""  # Initialize as empty
        call["ResolvedBy"] = ""  # Initialize as empty
        self.calls.append(call)
        self.undo_stack.append(("add", call))

    def resolve_call(self, call_id, resolved_by):
        for call in self.calls:
            if call["CallID"] == call_id:
                call["ResolutionStatus"] = True
                call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                call["ResolvedBy"] = resolved_by
                self.undo_stack.append(("resolve", call))
                break

    def modify_call(self, call_id, updated_call):
        for call in self.calls:
            if call["CallID"] == call_id:
                self.undo_stack.append(("modify", call.copy()))
                call.update(updated_call)
                break

    def undo(self):
        if not self.undo_stack:
            return
        action, call = self.undo_stack.pop()
        if action == "add":
            self.calls.remove(call)
            self.redo_stack.append(("add", call))
        elif action == "resolve":
            call["ResolutionStatus"] = False
            call["ResolutionTimestamp"] = ""
            call["ResolvedBy"] = ""
            self.redo_stack.append(("resolve", call))
        elif action == "modify":
            for c in self.calls:
                if c["CallID"] == call["CallID"]:
                    self.redo_stack.append(("modify", c.copy()))
                    c.update(call)
                    break

    def redo(self):
        if not self.redo_stack:
            return
        action, call = self.redo_stack.pop()
        if action == "add":
            self.calls.append(call)
            self.undo_stack.append(("add", call))
        elif action == "resolve":
            call["ResolutionStatus"] = True
            call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.undo_stack.append(("resolve", call))
        elif action == "modify":
            for c in self.calls:
                if c["CallID"] == call["CallID"]:
                    self.undo_stack.append(("modify", c.copy()))
                    c.update(call)
                    break

    def save_to_file(self, filename, filetype="txt"):
        if filetype == "txt":
            with open(filename, "w") as file:
                for call in self.calls:
                    file.write(json.dumps(call) + "\n")
        elif filetype == "csv":
            with open(filename, "w", newline="") as file:
                fieldnames = [
                    "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                    "InputMedium", "Source", "Caller", "Location", "Code", "Description", "ResolvedBy"
                ]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.calls)
        self.last_saved_hash = self._calculate_hash()

    def load_from_file(self, filename, filetype="txt"):
        try:
            self.calls = []
            if filetype == "txt":
                with open(filename, "r") as file:
                    for line in file:
                        self.calls.append(json.loads(line.strip()))
            elif filetype == "csv":
                with open(filename, "r") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        self.calls.append(row)
            self.last_saved_hash = self._calculate_hash()

            # Update the report_counter based on the loaded data
            self._update_report_counter()
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False

    def _update_report_counter(self):
        # Find the highest CallID in the loaded data and update report_counter
        if self.calls:
            last_call_id = max(int(call["CallID"][4:]) for call in self.calls)  # Extract numeric part of CallID
            self.report_counter = last_call_id + 1  # Set counter to the next available number
        else:
            self.report_counter = 1  # If no calls are loaded, start from 1

    def _calculate_hash(self):
        # Calculate a hash of the current data to detect changes
        data = json.dumps(self.calls, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()


class DispatchCallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dispatch Call Management System")
        self.manager = DispatchCallManager()

        # Track the last loaded file's hash
        self.last_loaded_hash = None

        # Create the log area before loading autosave
        self.create_log_area()  # Ensure log area is created first

        # Create the table before loading autosave
        self.create_table()  # Ensure table is created before update_table is called

        # Load autosave.txt on launch
        self.load_autosave()

        # Login
        self.login()

        # Input Fields
        self.input_medium_var = tk.StringVar(value="Radio")  # Default input medium
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar(value="A")  # Default location
        self.code_var = tk.StringVar(value="Green")  # Default code
        self.description_var = tk.StringVar()

        # GUI Layout
        self.create_input_fields()
        self.create_buttons()

        # Start the data reload loop every 125 ms
        self.root.after(125, self.reload_data_loop)

    def load_autosave(self):
        try:
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = self.manager._calculate_hash()  # Update the last loaded hash
                self.log("Autosave loaded successfully.")
                self.update_table()  # Refresh the table if autosave is loaded
            else:
                self.log("Failed to load autosave.")
        except FileNotFoundError:
            self.log("Autosave file not found. Starting with empty data.")

    def login(self):
        username = simpledialog.askstring("Login", "Enter your username:", parent=self.root)
        if username:
            self.manager.set_user(username)
            self.log(f"User '{username}' logged in.")
        else:
            self.root.destroy()

    def create_input_fields(self):
        fields_frame = ttk.LabelFrame(self.root, text="New Dispatch Call")
        fields_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Input Medium dropdown
        ttk.Label(fields_frame, text="Input Medium:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        input_medium_options = ["Radio", "Social Media"]
        input_medium_dropdown = ttk.Combobox(fields_frame, textvariable=self.input_medium_var, values=input_medium_options)
        input_medium_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        input_medium_dropdown.bind("<<ComboboxSelected>>", self.update_source_and_location_options)

        # Source dropdown
        ttk.Label(fields_frame, text="Source:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.source_dropdown = ttk.Combobox(fields_frame, textvariable=self.source_var)
        self.source_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Caller entry
        ttk.Label(fields_frame, text="Caller:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(fields_frame, textvariable=self.caller_var).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Location dropdown
        ttk.Label(fields_frame, text="Location:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.location_dropdown = ttk.Combobox(fields_frame, textvariable=self.location_var)
        self.location_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Code dropdown
        ttk.Label(fields_frame, text="Code:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        code_options = ["Green", "Orange", "Red", "Purple", "Silver", "Adam", "Blue", "Yellow", "P1", "P2", "P3"]
        ttk.Combobox(fields_frame, textvariable=self.code_var, values=code_options).grid(row=4, column=1, padx=5, pady=5, sticky="w")

        # Description text area
        ttk.Label(fields_frame, text="Description:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, width=40, height=5)  # Default font
        self.description_entry.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        # Initialize source and location options based on default input medium
        self.update_source_and_location_options()

    def update_source_and_location_options(self, event=None):
        # Update source and location options based on the selected input medium
        input_medium = self.input_medium_var.get()
        if input_medium == "Radio":
            self.source_dropdown["values"] = ["Safety", "General", "First Aid"]
            self.location_dropdown["values"] = ["A", "B", "C", "D", "E", "F", "G"]
        elif input_medium == "Social Media":
            self.source_dropdown["values"] = ["Phone", "SMS", "Discord"]
            self.location_dropdown["values"] = ["H", "I", "J", "K", "L", "M", "N"]

        # Set default values for source and location
        self.source_var.set(self.source_dropdown["values"][0])
        self.location_var.set(self.location_dropdown["values"][0])

    def create_buttons(self):
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        ttk.Button(buttons_frame, text="Add Call", command=self.add_call).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Resolve Call", command=self.resolve_call).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Modify Call", command=self.modify_call).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Undo", command=self.manager.undo).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Redo", command=self.manager.redo).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Save", command=self.save_data).grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Load", command=self.load_data).grid(row=0, column=6, padx=5, pady=5)

    def create_table(self):
        self.table = ttk.Treeview(
            self.root,
            columns=(
                "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                "InputMedium", "Source", "Caller", "Location", "Code", "Description", "ResolvedBy"
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
            ("Code", "Code"),  # Added Code column
            ("Description", "Description"),
            ("ResolvedBy", "Resolved By")
        ]
        for col, heading in columns:
            self.table.heading(col, text=heading)
            self.table.column(col, width=120)

        self.table.bind("<Double-1>", self.show_full_description)  # Double-click to show full description
        self.update_table()

    def update_table(self):
        for row in self.table.get_children():
            self.table.delete(row)
        for call in self.manager.calls:
            resolved = call.get("ResolutionStatus", False)
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
                call["Code"],  # Display Code
                call["Description"],
                call.get("ResolvedBy", "")
            ), tags=("resolved" if resolved else "unresolved"))

        # Change background color of resolved Call IDs
        self.table.tag_configure("resolved", background="light green")

        # Scroll to the bottom of the table to show the latest entry
        if self.table.get_children():
            self.table.see(self.table.get_children()[-1])  # Scroll to the last row

    def show_full_description(self, event):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            for call in self.manager.calls:
                if call["CallID"] == call_id:
                    description = call["Description"]
                    self._open_description_window(description)
                    break

    def _open_description_window(self, description):
        window = tk.Toplevel(self.root)
        window.title("Full Description")
        text = scrolledtext.ScrolledText(window, width=60, height=20)  # Default font

        # Append the current user's name to the description
        full_description = f"{description}"
        text.insert(tk.END, full_description)
        text.config(state=tk.DISABLED)  # Make it read-only
        text.pack(padx=10, pady=10)

    def save_and_reload(self):
        # Save the data to the autosave file
        self.manager.save_to_file("autosave.txt")
        self.manager.save_to_file("autosave.csv", filetype="csv")  # Save to CSV as well
        self.log("Autosave completed.")

        # Reload the data from the autosave file
        if self.manager.load_from_file("autosave.txt", filetype="txt"):
            self.update_table()  # Refresh the table
            self.log("Data reloaded successfully.")
        else:
            self.log("Failed to reload data.")

    def reload_data_loop(self):
        # Check if the autosave file has changed
        current_hash = self._calculate_file_hash("autosave.txt")
        if current_hash != self.last_loaded_hash:
            # Reload the data if the file has changed
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = current_hash  # Update the last loaded hash
                self.update_table()  # Refresh the table
                self.log("Data reloaded due to changes in autosave file.")

        # Schedule the next reload check
        self.root.after(125, self.reload_data_loop)

    def _calculate_file_hash(self, filename):
        # Calculate the hash of the file to detect changes
        try:
            with open(filename, "rb") as file:
                file_content = file.read()
                return hashlib.md5(file_content).hexdigest()
        except FileNotFoundError:
            return None  # File does not exist

    def add_call(self):
        call = {
            "InputMedium": self.input_medium_var.get(),
            "Source": self.source_var.get(),
            "Caller": self.caller_var.get(),
            "Location": self.location_var.get(),
            "Code": self.code_var.get(),
            "Description": self.description_entry.get("1.0", tk.END).strip(),
            "ResolutionStatus": False
        }
        self.manager.add_call(call)
        self.save_and_reload()  # Autosave and reload after adding a call
        self.log(f"Call added: {call['CallID']}")

    def resolve_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            resolved_by = simpledialog.askstring("Resolve Call", "Enter the name who resolved the call:", parent=self.root)
            if resolved_by:
                self.manager.resolve_call(call_id, resolved_by)
                self.save_and_reload()  # Autosave and reload after resolving a call
                self.log(f"Call resolved: {call_id} by {resolved_by}")

    def modify_call(self):
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            updated_call = {
                "InputMedium": self.input_medium_var.get(),
                "Source": self.source_var.get(),
                "Caller": self.caller_var.get(),
                "Location": self.location_var.get(),
                "Code": self.code_var.get(),
                "Description": self.description_entry.get("1.0", tk.END).strip()
            }
            self.manager.modify_call(call_id, updated_call)
            self.save_and_reload()  # Autosave and reload after modifying a call
            self.log(f"Call modified: {call_id}")

    def save_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            self.manager.save_to_file(filename, filetype)
            self.log(f"Data saved to {filename}")

    def load_data(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            if self.manager.load_from_file(filename, filetype):
                self.update_table()
                self.log(f"Data loaded from {filename}")
            else:
                self.log(f"Failed to load data from {filename}")

    def create_log_area(self):
        self.log_area = scrolledtext.ScrolledText(self.root, width=80, height=10)
        self.log_area.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")
        self.log_area.config(state=tk.DISABLED)  # Make it read-only

    def log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.see(tk.END)  # Scroll to the bottom to show the latest message


if __name__ == "__main__":
    root = tk.Tk()
    app = DispatchCallApp(root)
    root.mainloop()