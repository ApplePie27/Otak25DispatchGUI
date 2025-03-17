import json
import csv
from datetime import datetime
import hashlib
import random  # For generating random characters

class DispatchCallManager:
    def __init__(self):
        """Initialize the DispatchCallManager with empty data structures."""
        self.calls = []
        self.report_counter = 1  # Initialize the counter
        self.current_user = None  # Track the current user
        self.last_saved_hash = None  # Track the last saved state

    def set_user(self, username):
        """Set the current user."""
        if not username:
            raise ValueError("Username cannot be empty.")
        self.current_user = username

    def add_call(self, call):
        """Add a new call to the system."""
        if not call or not isinstance(call, dict):
            raise ValueError("Call must be a non-empty dictionary.")
        
        call["CallID"] = f"DC25{self.report_counter:04d}"  # Format CallID as DC250001, DC250002, etc.
        self.report_counter += 1  # Increment the counter for the next call
        call["CallDate"] = datetime.now().strftime("%Y-%m-%d")  # Date only
        call["CallTime"] = datetime.now().strftime("%H:%M")  # Time without seconds
        call["ResolutionTimestamp"] = ""  # Initialize as empty
        call["ResolvedBy"] = ""  # Initialize as empty
        call["CreatedBy"] = self.current_user  # Track who created the call
        call["ModifiedBy"] = ""  # Initialize ModifiedBy as empty
        call["RedFlag"] = False  # Initialize RedFlag as False
        call["ReportNumber"] = ""  # Initialize ReportNumber as empty
        self.calls.append(call)

    def red_flag_call(self, call_id):
        """Toggle the red flag status of a call."""
        if not call_id:
            raise ValueError("Call ID cannot be empty.")
    
        for call in self.calls:
            if call["CallID"] == call_id:
                if call["RedFlag"]:
                    # If already red-flagged, remove the red flag and report number
                    call["RedFlag"] = False
                    call["ReportNumber"] = ""
                else:
                    # If not red-flagged, add the red flag and generate a report number
                    call["RedFlag"] = True
                    call["ReportNumber"] = self._generate_short_report_number()
                call["ModifiedBy"] = self.current_user  # Track who modified the call
                break

    def _generate_short_report_number(self):
        """Generate a shorter, unique report number (6 characters)."""
        # Use a combination of timestamp and random characters
        timestamp = datetime.now().strftime("%H%M%S")  # Hours, minutes, seconds
        random_chars = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=3))  # 3 random characters
        return f"{timestamp[:4]}{random_chars}"  # Combine to make 6 characters

    def resolve_call(self, call_id, resolved_by):
        """Resolve a call by marking it as resolved."""
        if not call_id or not resolved_by:
            raise ValueError("Call ID and resolved_by cannot be empty.")
        
        for call in self.calls:
            if call["CallID"] == call_id:
                call["ResolutionStatus"] = True
                call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                call["ResolvedBy"] = resolved_by
                call["ModifiedBy"] = self.current_user  # Track who resolved the call
                break

    def modify_call(self, call_id, updated_call):
        """Modify an existing call."""
        if not call_id or not updated_call or not isinstance(updated_call, dict):
            raise ValueError("Call ID and updated_call must be valid.")
        
        for call in self.calls:
            if call["CallID"] == call_id:
                call.update(updated_call)
                call["ModifiedBy"] = self.current_user  # Track who modified the call
                break

    def delete_call(self, call_id):
        """Delete a call from the system."""
        if not call_id:
            raise ValueError("Call ID cannot be empty.")
        
        for call in self.calls:
            if call["CallID"] == call_id:
                self.calls.remove(call)
                break

    def save_to_file(self, filename, filetype="txt"):
        """Save calls to a file."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
        try:
            if filetype == "txt":
                with open(filename, "w") as file:
                    for call in self.calls:
                        file.write(json.dumps(call) + "\n")
            elif filetype == "csv":
                with open(filename, "w", newline="") as file:
                    fieldnames = [
                        "CallID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
                        "InputMedium", "Source", "Caller", "Location", "Code", "Description", "ResolvedBy",
                        "CreatedBy", "ModifiedBy", "RedFlag", "ReportNumber"
                    ]
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.calls)
            self.last_saved_hash = self._calculate_hash()
        except Exception as e:
            raise Exception(f"Failed to save file: {e}")

    def load_from_file(self, filename, filetype="txt"):
        """Load calls from a file."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
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
            self._update_report_counter()
            return True
        except FileNotFoundError:
            return False  # File does not exist
        except Exception as e:
            raise Exception(f"Error loading file: {e}")

    def _update_report_counter(self):
        """Update the report counter based on the loaded data."""
        if self.calls:
            last_call_id = max(int(call["CallID"][4:]) for call in self.calls)  # Extract numeric part of CallID
            self.report_counter = last_call_id + 1  # Set counter to the next available number
        else:
            self.report_counter = 1  # If no calls are loaded, start from 1

    def _calculate_hash(self):
        """Calculate a hash of the current data to detect changes."""
        data = json.dumps(self.calls, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()