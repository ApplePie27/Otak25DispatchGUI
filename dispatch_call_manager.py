import json
import csv
from datetime import datetime
import hashlib
import random
import pickle
import threading
from filelock import FileLock, Timeout

class DispatchCallManager:
    def __init__(self):
        """Initialize the DispatchCallManager with empty data structures and a lock for thread safety."""
        self.calls = []
        self.report_counter = 1
        self.last_saved_hash = None
        self.lock = threading.Lock() # For thread-safety within an instance

    def add_call(self, call, current_user):
        if not current_user:
            raise ValueError("Current user not set. Please set a user before adding calls.")
        call_id = f"DC25{self.report_counter:04d}"
        call["CallID"] = call_id
        now = datetime.now()
        call["CallDate"] = now.strftime("%Y-%m-%d")
        call["CallTime"] = now.strftime("%H:%M")
        call["ResolutionTimestamp"] = ""
        call["ResolvedBy"] = ""
        call["CreatedBy"] = current_user
        call["ModifiedBy"] = ""
        call["RedFlag"] = False
        call["ReportNumber"] = ""
        call["Deleted"] = False
        self.calls.append(call)
        self.report_counter += 1
        return call_id

    def modify_call(self, call_id, updated_call, current_user):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call.update(updated_call)
                call["ModifiedBy"] = current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def resolve_call(self, call_id, resolved_by, current_user):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call["ResolutionStatus"] = True
                call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                call["ResolvedBy"] = resolved_by
                call["ModifiedBy"] = current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def delete_call(self, call_id, current_user):
        for call in self.calls:
            if call["CallID"] == call_id and not call.get("Deleted", False):
                call["Deleted"] = True
                call["ModifiedBy"] = current_user
                return True
        raise ValueError(f"No active call found with CallID: {call_id}")

    def restore_call(self, call_id, current_user):
        for call in self.calls:
            if call["CallID"] == call_id and call.get("Deleted", False):
                call["Deleted"] = False
                call["ModifiedBy"] = current_user
                return True
        raise ValueError(f"No deleted call found with CallID: {call_id}")

    def red_flag_call(self, call_id, current_user):
        for call in self.calls:
            if call["CallID"] == call_id:
                if not call.get("RedFlag", False):
                    call["RedFlag"] = True
                    call["ReportNumber"] = self._generate_short_report_number()
                else:
                    call["RedFlag"] = False
                    call["ReportNumber"] = ""
                call["ModifiedBy"] = current_user
                return True
        raise ValueError(f"No call found with CallID: {call_id}")

    def _generate_short_report_number(self):
        timestamp = datetime.now().strftime("%H%M%S")
        rand_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=3))
        return timestamp[:4] + rand_chars

    def save_to_file(self, filename, filetype="bin"):
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
        lock_path = f"{filename}.lock"
        lock = FileLock(lock_path, timeout=10)

        try:
            with lock:
                # If saving, we might need to load first to merge changes
                if os.path.exists(filename):
                    current_calls_on_disk = self._load_calls_from_disk(filename, filetype)
                    self._merge_calls(current_calls_on_disk)

                with self.lock: # Internal lock for data consistency
                    try:
                        if filetype == "bin":
                            with open(filename, "wb") as file:
                                pickle.dump({
                                    'calls': self.calls,
                                    'report_counter': self.report_counter
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
        except Timeout:
            raise Exception("Could not acquire file lock. Another user may be saving. Please try again.")

    def load_from_file(self, filename, filetype="bin"):
        if not filename:
            raise ValueError("Filename cannot be empty.")
        
        lock_path = f"{filename}.lock"
        lock = FileLock(lock_path, timeout=10)
        
        try:
            with lock:
                with self.lock: # Internal lock for data consistency
                    try:
                        self.calls = self._load_calls_from_disk(filename, filetype)
                        self._update_report_counter()
                        self.last_saved_hash = self._calculate_hash()
                        return True
                    except FileNotFoundError:
                        return False
                    except Exception as e:
                        raise Exception(f"Error loading file: {e}")
        except Timeout:
            raise Exception("Could not acquire file lock. Another user may be accessing the file. Please try again.")

    def _load_calls_from_disk(self, filename, filetype):
        """Helper to load calls without acquiring a new lock."""
        calls = []
        try:
            if filetype == "bin":
                with open(filename, "rb") as file:
                    data = pickle.load(file)
                    calls = data.get('calls', [])
            elif filetype == "txt":
                with open(filename, "r") as file:
                    for line in file:
                        call = json.loads(line.strip())
                        calls.append(call)
            elif filetype == "csv":
                with open(filename, "r") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        row["ResolutionStatus"] = row["ResolutionStatus"] == "True"
                        row["RedFlag"] = row["RedFlag"] == "True"
                        row["Deleted"] = row["Deleted"] == "True"
                        calls.append(row)
            return calls
        except FileNotFoundError:
            return []


    def _merge_calls(self, disk_calls):
        """Merge calls from disk with in-memory calls."""
        with self.lock:
            # Create a dictionary of current in-memory calls for quick lookup
            memory_calls_dict = {call['CallID']: call for call in self.calls}

            # Iterate through calls from the disk
            for disk_call in disk_calls:
                call_id = disk_call['CallID']
                if call_id in memory_calls_dict:
                    # If call exists, update it only if the disk version is "more recent"
                    # A simple timestamp or version number would be better, but we can use hash for now.
                    # For simplicity, we assume the disk has a more complete picture.
                    # A better strategy is needed for true conflict resolution (e.g., last-write-wins)
                    memory_calls_dict[call_id] = disk_call
                else:
                    # If call is new, add it
                    memory_calls_dict[call_id] = disk_call

            self.calls = list(memory_calls_dict.values())
            self._update_report_counter()


    def _update_report_counter(self):
        """Update the report counter based on the loaded data."""
        if self.calls:
            numeric_ids = [
                int(call["CallID"][4:])
                for call in self.calls
                if "CallID" in call and call["CallID"].startswith("DC25")
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