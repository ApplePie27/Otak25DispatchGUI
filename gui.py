import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from dispatch_call_manager import DispatchCallManager
from utils import calculate_file_hash
from datetime import datetime

class DispatchCallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dispatch Call Management System")

        # Allow the window to be resized
        self.root.resizable(True, True)

        self.manager = DispatchCallManager()
        self.last_loaded_hash = None

        # Create the log area and table before loading autosave
        self.create_log_area()
        self.create_table()

        # Load autosave.txt on launch
        self.load_autosave()

        # Login
        self.login()

        # Input Fields
        self.input_medium_var = tk.StringVar(value="Radio")
        self.source_var = tk.StringVar()
        self.caller_var = tk.StringVar()
        self.location_var = tk.StringVar(value="A")
        self.code_var = tk.StringVar(value="Green")
        self.description_var = tk.StringVar()

        # GUI Layout
        self.create_input_fields()
        self.create_buttons()
        self.create_search_bar()

        # Keyboard shortcuts
        self.root.bind("<Control-s>", lambda event: self.save_data())
        self.root.bind("<Control-l>", lambda event: self.load_data())
        self.root.bind("<Control-z>", lambda event: self.manager.undo())
        self.root.bind("<Control-y>", lambda event: self.manager.redo())

        # Configure grid weights for resizing
        self.configure_grid_weights()

        # Start the data reload loop every 125 ms
        self.root.after(125, self.reload_data_loop)

    def configure_grid_weights(self):
        """Configure grid weights to make the UI resizable."""
        # Make the table and log area expand with the window
        self.root.grid_rowconfigure(2, weight=1)  # Table row
        self.root.grid_rowconfigure(4, weight=1)  # Log area row
        self.root.grid_columnconfigure(0, weight=1)  # Single column

    def load_autosave(self):
        """Load data from the autosave file. If the file doesn't exist, initialize an empty dataset."""
        try:
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = self.manager._calculate_hash()
                self.log("Autosave loaded successfully.")
                self.update_table()
            else:
                self.log("Failed to load autosave.")
        except FileNotFoundError:
            # If the autosave file doesn't exist, initialize an empty dataset
            self.manager.calls = []  # Reset calls to an empty list
            self.manager.report_counter = 1  # Reset the report counter
            self.last_loaded_hash = self.manager._calculate_hash()  # Update the hash
            self.log("Autosave file not found. Starting with empty data.")
        except Exception as e:
            self.log(f"Error loading autosave: {e}")

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
        code_options = ["Green", "Orange", "Red", "Purple", "Silver", "Adam", "Blue", "Yellow", "P1", "P2", "P3"]
        ttk.Combobox(fields_frame, textvariable=self.code_var, values=code_options).grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        # Description text area
        ttk.Label(fields_frame, text="Description:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.description_entry = scrolledtext.ScrolledText(fields_frame, width=40, height=5)
        self.description_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        # Initialize source and location options based on default input medium
        self.update_source_and_location_options()

    def update_source_and_location_options(self, event=None):
        """Update source and location options based on the selected input medium."""
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
        """Create buttons for managing calls."""
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        ttk.Button(buttons_frame, text="Add Call", command=self.add_call).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Resolve Call", command=self.resolve_call).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Modify Call", command=self.modify_call).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Undo", command=self.manager.undo).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Redo", command=self.manager.redo).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Save", command=self.save_data).grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Load", command=self.load_data).grid(row=0, column=6, padx=5, pady=5)

    def create_table(self):
        """Create the table to display calls."""
        self.table = ttk.Treeview(
            self.root,
            columns=(
                "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                "InputMedium", "Source", "Caller", "Location", "Code", "Description", "ResolvedBy",
                "CreatedBy", "ModifiedBy"
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
            ("ModifiedBy", "Modified By")
        ]
        for col, heading in columns:
            self.table.heading(col, text=heading)
            if col == "Description":
                self.table.column(col, width=120, anchor="w")
            else:
                self.table.column(col, width=120, anchor="center")

        self.table.bind("<Double-1>", self.show_full_description)
        self.update_table()

    def update_table(self, filter_text=None):
        """Update the table with the latest calls."""
        for row in self.table.get_children():
            self.table.delete(row)

        # Filter calls based on search text
        filtered_calls = self.manager.calls
        if filter_text:
            filtered_calls = [
                call for call in self.manager.calls
                if filter_text.lower() in call["CallID"].lower() or
                filter_text.lower() in call["Caller"].lower() or
                filter_text.lower() in call["Description"].lower()
            ]

        # Populate the table with filtered calls
        for call in filtered_calls:
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
                call["Code"],
                call["Description"],
                call.get("ResolvedBy", ""),
                call.get("CreatedBy", ""),
                call.get("ModifiedBy", "")
            ), tags=("resolved" if resolved else "unresolved"))

        # Change background color of resolved Call IDs
        self.table.tag_configure("resolved", background="light green")

        # Scroll to the bottom of the table to show the latest entry
        if self.table.get_children():
            self.table.see(self.table.get_children()[-1])

    def show_full_description(self, event):
        """Show the full description of a call in a new window."""
        selected = self.table.selection()
        if selected:
            call_id = self.table.item(selected[0], "values")[0]
            for call in self.manager.calls:
                if call["CallID"] == call_id:
                    description = call["Description"]
                    self._open_description_window(description)
                    break

    def _open_description_window(self, description):
        """Open a new window to display the full description."""
        window = tk.Toplevel(self.root)
        window.title("Full Description")
        text = scrolledtext.ScrolledText(window, width=60, height=20)
        text.insert(tk.END, description)
        text.config(state=tk.DISABLED)
        text.pack(padx=10, pady=10)

    def save_and_reload(self):
        """Save the data and reload it."""
        self.manager.save_to_file("autosave.txt")
        self.manager.save_to_file("autosave.csv", filetype="csv")
        self.log("Autosave completed.")

        if self.manager.load_from_file("autosave.txt", filetype="txt"):
            self.update_table()
            self.log("Data reloaded successfully.")
        else:
            self.log("Failed to reload data.")

    def reload_data_loop(self):
        """Reload data from the autosave file if it has changed."""
        current_hash = calculate_file_hash("autosave.txt")
        if current_hash != self.last_loaded_hash:
            if self.manager.load_from_file("autosave.txt", filetype="txt"):
                self.last_loaded_hash = current_hash
                self.update_table()
                self.log("Data reloaded due to changes in autosave file.")

        # Schedule the next reload check
        self.root.after(125, self.reload_data_loop)

    def add_call(self):
        """Add a new call."""
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
        self.save_and_reload()
        self.log(f"Call added: {call['CallID']}")

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
                "Description": self.description_entry.get("1.0", tk.END).strip()
            }
            self.manager.modify_call(call_id, updated_call)
            self.save_and_reload()
            self.log(f"Call modified: {call_id}")

    def save_data(self):
        """Save data to a file."""
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            self.manager.save_to_file(filename, filetype)
            self.log(f"Data saved to {filename}")

    def load_data(self):
        """Load data from a file."""
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
        if filename:
            filetype = "txt" if filename.endswith(".txt") else "csv"
            if self.manager.load_from_file(filename, filetype):
                self.update_table()
                self.log(f"Data loaded from {filename}")
            else:
                self.log(f"Failed to load data from {filename}")

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