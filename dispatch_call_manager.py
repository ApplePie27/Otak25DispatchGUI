import json
import csv
from datetime import datetime
import hashlib
import random
import pickle
import threading

class DispatchCallManager:
    def __init__(self):
        """Initialize the DispatchCallManager with empty data structures and a lock for thread safety."""
        self.calls = []
        self.report_counter = 1
        self.current_user = None
        self.last_saved_hash = None
        self.lock = threading.Lock()

    def set_user(self, username):
        if not username:
            raise ValueError("Username cannot be empty.")
        self.current_user = username

    def add_call(self, call):
        if not self.current_user:
            raise ValueError("Current user not set. Please set a user before adding calls.")
        call_id = f"DC25{self.report_counter:04d}"
        call["CallID"] = call_id
        now = datetime.now()
        call["CallDate"] = now.strftime("%Y-%m-%d")
        call["CallTime"] = now.strftime("%H:%M")
        call["ResolutionTimestamp"] = ""
        call["ResolvedBy"] = ""
        call["CreatedBy"] = self.current_user
        call["ModifiedBy"] = ""
        call["RedFlag"] = False
        call["ReportNumber"] = ""
        call["Deleted"] = False
        self.calls.append(call)
        self.report_counter += 1
        return call_id

    def modify_call(self, call_id, updated_call):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call.update(updated_call)
                call["ModifiedBy"] = self.current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def resolve_call(self, call_id, resolved_by):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call["ResolutionStatus"] = True
                call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                call["ResolvedBy"] = resolved_by
                call["ModifiedBy"] = self.current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def delete_call(self, call_id):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call["Deleted"] = True
                call["ModifiedBy"] = self.current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def restore_call(self, call_id):
        for call in self.calls:
            if call["CallID"] == call_id and call.get("Deleted", False):
                call["Deleted"] = False
                call["ModifiedBy"] = self.current_user
                return True
        raise ValueError(f"No deleted call found with CallID: {call_id}")

    def red_flag_call(self, call_id):
        for call in self.calls:
            if call["CallID"] == call_id:
                if not call.get("RedFlag", False):
                    call["RedFlag"] = True
                    call["ReportNumber"] = self._generate_short_report_number()
                else:
                    call["RedFlag"] = False
                    call["ReportNumber"] = ""
                call["ModifiedBy"] = self.current_user
                return True
        raise ValueError(f"No call found with CallID: {call_id}")

    def _generate_short_report_number(self):
        timestamp = datetime.now().strftime("%H%M%S")
        rand_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=3))
        return timestamp[:4] + rand_chars

    def save_to_file(self, filename, filetype="bin"):
        """Save calls to a file with thread-safe locking."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        with self.lock:
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
        """Load calls from a file with thread-safe locking."""
        if not filename:
            raise ValueError("Filename cannot be empty.")
        with self.lock:
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
                            if "RedFlag" not in call:
                                call["RedFlag"] = False
                            self.calls.append(call)
                    self._update_report_counter()
                elif filetype == "csv":
                    with open(filename, "r") as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            row["ResolutionStatus"] = row["ResolutionStatus"] == "True"
                            row["RedFlag"] = row["RedFlag"] == "True"
                            row["Deleted"] = row["Deleted"] == "True"
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
            numeric_ids = [
                int(call["CallID"][4:])
                for call in self.calls
                if not call.get("Deleted", False) and "CallID" in call
            ]
            if numeric_ids:
                self.report_counter = max(numeric_ids) + 1
            else:
                self.report_counter = 1
        else:
            self.report_counter = 1

    def _calculate_hash(self):
        """Calculate a hash of the current data to detect changes."""
        data = json.dumps(self.calls, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def get_data_hash(self):
        """Get the current hash of the data."""
        return self._calculate_hash()