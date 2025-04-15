import json
import csv
from datetime import datetime
import hashlib
import random
import pickle

class DispatchCallManager:
    def __init__(self):
        """Initialize the DispatchCallManager with empty data structures."""
        self.calls = []
        self.report_counter = 1
        self.current_user = None
        self.last_saved_hash = None

    def set_user(self, username):
        """Set the current user."""
        if not username:
            raise ValueError("Username cannot be empty.")
        self.current_user = username

    def add_call(self, call):
        """Add a new call to the system."""
        if not call or not isinstance(call, dict):
            raise ValueError("Call must be a non-empty dictionary.")
        
        call["CallID"] = f"DC25{self.report_counter:04d}"
        self.report_counter += 1
        call["CallDate"] = datetime.now().strftime("%Y-%m-%d")
        call["CallTime"] = datetime.now().strftime("%H:%M")
        call["ResolutionTimestamp"] = ""
        call["ResolvedBy"] = ""
        call["CreatedBy"] = self.current_user
        call["ModifiedBy"] = ""
        call["RedFlag"] = False
        call["ReportNumber"] = ""
        call["Deleted"] = False
        self.calls.append(call)

    def red_flag_call(self, call_id):
        """Toggle the red flag status of a call."""
        if not call_id:
            raise ValueError("Call ID cannot be empty.")
    
        for call in self.calls:
            if call["CallID"] == call_id and not call["Deleted"]:
                if call["RedFlag"]:
                    call["RedFlag"] = False
                    call["ReportNumber"] = ""
                else:
                    call["RedFlag"] = True
                    call["ReportNumber"] = self._generate_short_report_number()
                call["ModifiedBy"] = self.current_user
                break

    def _generate_short_report_number(self):
        """Generate a shorter, unique report number (6 characters)."""
        timestamp = datetime.now().strftime("%H%M%S")
        random_chars = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=3))
        return f"{timestamp[:4]}{random_chars}"

    def resolve_call(self, call_id, resolved_by):
        """Resolve a call by marking it as resolved."""
        if not call_id or not resolved_by:
            raise ValueError("Call ID and resolved_by cannot be empty.")
        
        for call in self.calls:
            if call["CallID"] == call_id and not call["Deleted"]:
                call["ResolutionStatus"] = True
                call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                call["ResolvedBy"] = resolved_by
                call["ModifiedBy"] = self.current_user
                break

    def modify_call(self, call_id, updated_call):
        """Modify an existing call."""
        if not call_id or not updated_call or not isinstance(updated_call, dict):
            raise ValueError("Call ID and updated_call must be valid.")
        
        for call in self.calls:
            if call["CallID"] == call_id and not call["Deleted"]:
                call.update(updated_call)
                call["ModifiedBy"] = self.current_user
                break

    def delete_call(self, call_id):
        """Mark a call as deleted rather than removing it."""
        if not call_id:
            raise ValueError("Call ID cannot be empty.")
        
        for call in self.calls:
            if call["CallID"] == call_id:
                call["Deleted"] = True
                call["ModifiedBy"] = self.current_user
                break

    def restore_call(self, call_id):
        """Restore a previously deleted call."""
        if not call_id:
            raise ValueError("Call ID cannot be empty.")
        
        for call in self.calls:
            if call["CallID"] == call_id:
                call["Deleted"] = False
                call["ModifiedBy"] = self.current_user
                break

    def save_to_file(self, filename, filetype="bin"):
        """Save calls to a file."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
        try:
            if filetype == "bin":
                with open(filename, "wb") as file:
                    pickle.dump({
                        'calls': self.calls,
                        'report_counter': self.report_counter,
                        'current_user': self.current_user
                    }, file)
            elif filetype == "txt":
                with open(filename, "w") as file:
                    for call in self.calls:
                        file.write(json.dumps(call) + "\n")
            elif filetype == "csv":
                with open(filename, "w", newline="") as file:
                    fieldnames = [
                        "CallID", "CallDate", "CallTime", "ResolutionTimestamp", 
                        "ResolutionStatus", "InputMedium", "Source", "Caller", 
                        "Location", "Code", "Description", "ResolvedBy",
                        "CreatedBy", "ModifiedBy", "RedFlag", "ReportNumber",
                        "Deleted"
                    ]
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    for call in self.calls:
                        row = {field: call.get(field, "") for field in fieldnames}
                        writer.writerow(row)
            self.last_saved_hash = self._calculate_hash()
        except Exception as e:
            raise Exception(f"Failed to save file: {e}")

    def load_from_file(self, filename, filetype="bin"):
        """Load calls from a file."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
        try:
            self.calls = []
            if filetype == "bin":
                with open(filename, "rb") as file:
                    data = pickle.load(file)
                    self.calls = data['calls']
                    self.report_counter = data['report_counter']
                    self.current_user = data['current_user']
            elif filetype == "txt":
                with open(filename, "r") as file:
                    for line in file:
                        call = json.loads(line.strip())
                        if "Deleted" not in call:
                            call["Deleted"] = False
                        self.calls.append(call)
                self._update_report_counter()
            elif filetype == "csv":
                with open(filename, "r") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        for field in ["ResolutionStatus", "RedFlag", "Deleted"]:
                            if field in row:
                                row[field] = row[field].lower() == "true"
                        self.calls.append(row)
                self._update_report_counter()
            self.last_saved_hash = self._calculate_hash()
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            raise Exception(f"Error loading file: {e}")

    def _update_report_counter(self):
        """Update the report counter based on the loaded data."""
        if self.calls:
            last_call_id = max(int(call["CallID"][4:]) for call in self.calls if not call.get("Deleted", False))
            self.report_counter = last_call_id + 1
        else:
            self.report_counter = 1

    def _calculate_hash(self):
        """Calculate a hash of the current data to detect changes."""
        data = json.dumps(self.calls, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()