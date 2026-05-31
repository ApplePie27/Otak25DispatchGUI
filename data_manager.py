import sqlite3
from datetime import datetime
import os

class DataManager:
    def __init__(self, db_filename):
        """Initialize the DataManager, connecting to the SQLite database with WAL enabled."""
        self.db_filename = db_filename
        self.conn = sqlite3.connect(db_filename, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.call_id_prefix = f"DC{datetime.now().strftime('%y')}"
        
        # Enable Write-Ahead Logging (WAL) for better concurrent performance
        with self.conn:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they do not exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    ReportID TEXT UNIQUE,
                    CallDate TEXT,
                    CallTime TEXT,
                    AnsweredTimestamp TEXT,
                    AnsweredStatus BOOLEAN,
                    AnsweredBy TEXT,
                    ResolutionTimestamp TEXT,
                    ResolutionStatus BOOLEAN,
                    ResolvedBy TEXT,
                    InputMedium TEXT,
                    Source TEXT,
                    Caller TEXT,
                    Location TEXT,
                    Code TEXT,
                    Description TEXT,
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
        self.conn.execute(
            "INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)",
            (call_id, timestamp, user, action, details)
        )

    def get_all_calls(self, sort_by="ReportID", sort_order="ASC"):
        """Fetch all non-deleted calls with sorting."""
        valid_columns = [
            "ReportID", "CallDate", "CallTime", "AnsweredTimestamp", "AnsweredStatus", "AnsweredBy",
            "ResolutionTimestamp", "ResolutionStatus", "ResolvedBy",
            "InputMedium", "Source", "Caller", "Location", "Code", "Description",
            "CreatedBy", "ModifiedBy", "RedFlag", "Deleted", "ReportNumber"
        ]
        if sort_by not in valid_columns:
            sort_by = "ReportID"
        
        sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
        
        # Filter out deleted elements to keep the active view clean
        query = f"SELECT * FROM calls WHERE Deleted = 0 OR Deleted IS NULL ORDER BY {sort_by} {sort_order}"
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
        """Add a new call to the database and generate a clean ReportID inside a transaction."""
        now = datetime.now()
        
        with self.conn: 
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO calls (
                    CallDate, CallTime, AnsweredTimestamp, AnsweredStatus, AnsweredBy,
                    ResolutionTimestamp, ResolutionStatus, ResolvedBy, InputMedium, Source, 
                    Caller, Location, Code, Description, CreatedBy, ModifiedBy, RedFlag,
                    ReportNumber, Deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "", False, "", "", False, "",
                call['InputMedium'], call['Source'], call['Caller'], call['Location'],
                call['Code'], call['Description'], current_user, "", False, "", False
            ))
            
            new_id = cursor.lastrowid
            report_id = f"{self.call_id_prefix}-{new_id:04d}"
            
            cursor.execute("UPDATE calls SET ReportID = ? WHERE ID = ?", (report_id, new_id))
            self._log_history(report_id, current_user, "Call Created")
        
        return report_id

    def modify_call(self, report_id, updated_call, current_user):
        """Modify an existing call and log the specific changes made."""
        original_call = self.get_call_by_id(report_id)
        if not original_call:
            raise ValueError(f"No call found with ReportID: {report_id}")
            
        modification_details = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Field comparison
        fields_to_check = ['InputMedium', 'Source', 'Caller', 'Location', 'Code']
        for field in fields_to_check:
            old_val = str(original_call[field])
            new_val = str(updated_call[field])
            if old_val != new_val:
                modification_details.append(f"{field}: '{old_val}' -> '{new_val}'")
        
        if original_call['Description'].strip() != updated_call['Description'].strip():
            modification_details.append("Description was updated.")

        # Handle RESOLVING a call
        is_newly_resolved = updated_call["ResolutionStatus"] and not original_call["ResolutionStatus"]
        if is_newly_resolved:
            updated_call["ResolutionTimestamp"] = now
            self._log_history(report_id, current_user, "Call Resolved", f"Resolved by: {updated_call['ResolvedBy']}")
        else:
            if not updated_call["ResolutionStatus"] and original_call["ResolutionStatus"]:
                modification_details.append("Status: 'Resolved' -> 'Un-resolved'")
                updated_call["ResolvedBy"] = "" 
                updated_call["ResolutionTimestamp"] = ""

        # Handle ANSWERING a call
        is_newly_answered = updated_call["AnsweredStatus"] and not original_call["AnsweredStatus"]
        if is_newly_answered:
            updated_call["AnsweredTimestamp"] = now
            self._log_history(report_id, current_user, "Call Answered", f"Answered by: {updated_call['AnsweredBy']}")
        else:
            if not updated_call["AnsweredStatus"] and original_call["AnsweredStatus"]:
                modification_details.append("Status: 'Answered' -> 'Un-answered'")
                updated_call["AnsweredBy"] = "" 
                updated_call["AnsweredTimestamp"] = ""

        if modification_details:
            details_string = "; ".join(modification_details)
            self._log_history(report_id, current_user, "Call Modified", details_string)
        
        updated_call['ModifiedBy'] = current_user
        
        with self.conn:
            self.conn.execute("""
                UPDATE calls SET
                InputMedium=?, Source=?, Caller=?, Location=?, Code=?, Description=?,
                AnsweredStatus=?, AnsweredBy=?, AnsweredTimestamp=?,
                ResolutionStatus=?, ResolvedBy=?, ResolutionTimestamp=?,
                ModifiedBy=?
                WHERE ReportID=?
            """, (
                updated_call['InputMedium'], updated_call['Source'], updated_call['Caller'],
                updated_call['Location'], updated_call['Code'], updated_call['Description'],
                updated_call['AnsweredStatus'], updated_call['AnsweredBy'], updated_call.get('AnsweredTimestamp', original_call['AnsweredTimestamp']),
                updated_call['ResolutionStatus'], updated_call['ResolvedBy'], updated_call.get('ResolutionTimestamp', original_call['ResolutionTimestamp']),
                updated_call['ModifiedBy'], report_id
            ))
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