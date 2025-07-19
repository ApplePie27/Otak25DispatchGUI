import sqlite3
from datetime import datetime
import random
import os
import shutil

class DataManager:
    def __init__(self, db_filename):
        """Initialize the DataManager, connecting to the SQLite database."""
        self.db_filename = db_filename
        self.conn = sqlite3.connect(db_filename, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.call_id_prefix = f"DC{datetime.now().strftime('%y')}"
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist. Now with an autoincrementing primary key."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    ReportID TEXT UNIQUE,
                    CallDate TEXT,
                    CallTime TEXT,
                    ResolutionTimestamp TEXT,
                    ResolutionStatus BOOLEAN,
                    InputMedium TEXT,
                    Source TEXT,
                    Caller TEXT,
                    Location TEXT,
                    Code TEXT,
                    Description TEXT,
                    ResolvedBy TEXT,
                    CreatedBy TEXT,
                    ModifiedBy TEXT,
                    RedFlag BOOLEAN,
                    ReportNumber TEXT,
                    Deleted BOOLEAN
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS call_history (
                    HistoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                    CallID TEXT,
                    Timestamp TEXT,
                    User TEXT,
                    Action TEXT,
                    Details TEXT
                )
            """)

    def _log_history(self, call_id, user, action, details=""):
        """Log an action to the call_history table."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            self.conn.execute(
                "INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)",
                (call_id, timestamp, user, action, details)
            )

    def get_all_calls(self, sort_by="ReportID", sort_order="ASC"):
        """Fetch all calls from the database, with sorting."""
        valid_columns = [
            "ReportID", "CallDate", "CallTime", "ResolutionTimestamp", "ResolutionStatus",
            "InputMedium", "Source", "Caller", "Location", "Code", "Description",
            "ResolvedBy", "CreatedBy", "ModifiedBy", "RedFlag", "Deleted", "ReportNumber"
        ]
        if sort_by not in valid_columns:
            sort_by = "ReportID"
        
        sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
        
        query = f"SELECT * FROM calls ORDER BY {sort_by} {sort_order}"
        cursor = self.conn.execute(query)
        return cursor.fetchall()

    def get_call_by_id(self, report_id):
        """Fetch a single call by its ReportID."""
        cursor = self.conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        return cursor.fetchone()

    def get_history_for_call(self, report_id):
        """Fetch the audit history for a specific call."""
        cursor = self.conn.execute("SELECT * FROM call_history WHERE CallID = ? ORDER BY Timestamp DESC", (report_id,))
        return cursor.fetchall()

    def add_call(self, call, current_user):
        """Add a new call to the database using a 2-step transaction to prevent race conditions."""
        now = datetime.now()
        
        with self.conn: 
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO calls (
                    CallDate, CallTime, ResolutionTimestamp, ResolutionStatus,
                    InputMedium, Source, Caller, Location, Code, Description,
                    ResolvedBy, CreatedBy, ModifiedBy, RedFlag, ReportNumber, Deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "", False,
                call['InputMedium'], call['Source'], call['Caller'], call['Location'],
                call['Code'], call['Description'], "", current_user, "", False, "", False
            ))
            
            new_id = cursor.lastrowid
            report_id = f"{self.call_id_prefix}-{new_id:04d}"
            
            cursor.execute("UPDATE calls SET ReportID = ? WHERE ID = ?", (report_id, new_id))
            
            self._log_history(report_id, current_user, "Call Created")
        
        return report_id

    # --- ARCHITECTURAL ENHANCEMENT ---
    # The modify_call method is now re-architected to generate detailed audit logs.
    def modify_call(self, report_id, updated_call, current_user):
        """Modify an existing call and log the specific changes made."""
        original_call = self.get_call_by_id(report_id)
        if not original_call:
            raise ValueError(f"No call found with ReportID: {report_id}")
            
        modification_details = []
        
        # 1. Check for changes in standard text fields
        fields_to_check = ['InputMedium', 'Source', 'Caller', 'Location', 'Code']
        for field in fields_to_check:
            old_val = str(original_call[field])
            new_val = str(updated_call[field])
            if old_val != new_val:
                modification_details.append(f"{field}: '{old_val}' -> '{new_val}'")
        
        # 2. Check for change in the multi-line description field
        if original_call['Description'].strip() != updated_call['Description'].strip():
            modification_details.append("Description was updated.")

        # 3. Handle the primary action of RESOLVING a call
        is_newly_resolved = updated_call["ResolutionStatus"] and not original_call["ResolutionStatus"]
        if is_newly_resolved:
            updated_call["ResolutionTimestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._log_history(report_id, current_user, "Call Resolved", f"Resolved by: {updated_call['ResolvedBy']}")
        
        # 4. Handle other changes related to resolution status
        else:
            # Check if a call was UN-resolved
            if not updated_call["ResolutionStatus"] and original_call["ResolutionStatus"]:
                modification_details.append("Status: 'Resolved' -> 'Un-resolved'")
                updated_call["ResolvedBy"] = "" # Clear the resolver when un-resolving
                updated_call["ResolutionTimestamp"] = ""

            # Check if the 'ResolvedBy' was changed on an already resolved call
            elif updated_call["ResolutionStatus"] and (original_call['ResolvedBy'] != updated_call['ResolvedBy']):
                old_resolver = original_call['ResolvedBy']
                new_resolver = updated_call['ResolvedBy']
                modification_details.append(f"ResolvedBy: '{old_resolver}' -> '{new_resolver}'")

        # 5. If any modifications were detected, log them.
        if modification_details:
            details_string = "; ".join(modification_details)
            self._log_history(report_id, current_user, "Call Modified", details_string)
        
        # 6. Finally, commit the update to the database
        updated_call['ModifiedBy'] = current_user
        
        with self.conn:
            self.conn.execute("""
                UPDATE calls SET
                InputMedium=?, Source=?, Caller=?, Location=?, Code=?, Description=?,
                ResolutionStatus=?, ResolvedBy=?, ResolutionTimestamp=?, ModifiedBy=?
                WHERE ReportID=?
            """, (
                updated_call['InputMedium'], updated_call['Source'], updated_call['Caller'],
                updated_call['Location'], updated_call['Code'], updated_call['Description'],
                updated_call['ResolutionStatus'], updated_call['ResolvedBy'],
                updated_call.get('ResolutionTimestamp', original_call['ResolutionTimestamp']),
                updated_call['ModifiedBy'], report_id
            ))
        return True


    def _update_call_flag(self, report_id, user, field, value, log_action):
        """Generic helper to update a boolean flag on a call."""
        allowed_fields = {"Deleted", "RedFlag"}
        if field not in allowed_fields:
            raise ValueError(f"Invalid field specified for flag update: {field}")

        with self.conn:
            self.conn.execute(
                f"UPDATE calls SET {field}=?, ModifiedBy=? WHERE ReportID=?",
                (value, user, report_id)
            )
            self._log_history(report_id, user, log_action)
        return True

    def delete_call(self, report_id, current_user):
        return self._update_call_flag(report_id, current_user, "Deleted", True, "Call Deleted")

    def restore_call(self, report_id, current_user):
        return self._update_call_flag(report_id, current_user, "Deleted", False, "Call Restored")

    def red_flag_call(self, report_id, current_user):
        """Toggle the red flag status for a call."""
        original_call = self.get_call_by_id(report_id)
        if not original_call:
            raise ValueError(f"No call found with ReportID: {report_id}")

        new_flag_status = not original_call['RedFlag']
        report_number = ""
        if new_flag_status:
            ts = datetime.now().strftime("%H%M%S")
            rand_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=3))
            report_number = ts[:4] + rand_chars
        
        with self.conn:
            self.conn.execute(
                "UPDATE calls SET RedFlag=?, ReportNumber=?, ModifiedBy=? WHERE ReportID=?",
                (new_flag_status, report_number, current_user, report_id)
            )
            action = "Red Flag Added" if new_flag_status else "Red Flag Removed"
            self._log_history(report_id, current_user, action, f"Report #: {report_number}")
        return True
        
    def create_backup(self, backup_dir, max_backups):
        """Create a backup of the database file using the online backup API."""
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = os.path.join(backup_dir, f"backup_{timestamp}.db")
        try:
            b_conn = sqlite3.connect(backup_filename)
            with b_conn:
                self.conn.backup(b_conn, pages=1, progress=None)
            b_conn.close()
            backup_files = sorted(
                [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")],
                key=os.path.getmtime
            )
            while len(backup_files) > max_backups:
                os.remove(backup_files.pop(0))
            return f"Backup created: {os.path.basename(backup_filename)}"
        except Exception as e:
            raise Exception(f"Failed to create backup: {e}")

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None