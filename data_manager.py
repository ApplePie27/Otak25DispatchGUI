"""
DATA_MANAGER.PY
Handles all SQLite database interactions.
Optimized heavily with SQLite PRAGMAs and a custom retry decorator 
to survive multi-computer concurrency over a spotty Windows SMB File Share.
"""
import sqlite3
from datetime import datetime
import os
import time
from functools import wraps

def sqlite_retry(max_retries=5, delay=0.5):
    """Intercepts 'Database Locked' errors over SMB and retries silently."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator

class DataManager:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        # timeout=20.0 prevents "Database Locked" errors by forcing laptops to wait 
        # up to 20 seconds in line to write to the database over the network.
        self.conn = sqlite3.connect(db_filename, check_same_thread=False, timeout=20.0)
        self.conn.row_factory = sqlite3.Row
        self.call_id_prefix = f"DC{datetime.now().strftime('%y')}" # Generates DC24, DC25, etc.
        
        # SQLite Network Optimization PRAGMAs
        with self.conn:
            self.conn.execute("PRAGMA journal_mode=TRUNCATE;") # Best for network drives
            self.conn.execute("PRAGMA synchronous=NORMAL;")
            self.conn.execute("PRAGMA busy_timeout=20000;")
            self.conn.execute("PRAGMA temp_store=MEMORY;")
            self.conn.execute("PRAGMA cache_size=-64000;")
            
        self._create_tables()

    def _create_tables(self):
        """Builds the database schema on first boot."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    ReportID TEXT UNIQUE, CallDate TEXT, CallTime TEXT,
                    AnsweredTimestamp TEXT, AnsweredStatus BOOLEAN, AnsweredBy TEXT,
                    ResolutionTimestamp TEXT, ResolutionStatus BOOLEAN, ResolvedBy TEXT,
                    InputMedium TEXT, Source TEXT, Caller TEXT, Location TEXT,
                    Code TEXT, Description TEXT, CreatedBy TEXT, ModifiedBy TEXT,
                    RedFlag BOOLEAN, ReportNumber TEXT, Deleted BOOLEAN
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS call_history (
                    HistoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                    CallID TEXT, Timestamp TEXT, User TEXT, Action TEXT, Details TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS passdown_notes (
                    NoteID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Timestamp TEXT, User TEXT, Note TEXT
                )
            """)
            
            # Legacy column upgrades. Wrapped in Try/Except so they don't crash if they already exist.
            try: self.conn.execute("ALTER TABLE calls ADD COLUMN DiscordMessageID TEXT;")
            except sqlite3.OperationalError: pass 

            try: self.conn.execute("ALTER TABLE calls ADD COLUMN DiscordChannelID TEXT;")
            except sqlite3.OperationalError: pass 

            try: self.conn.execute("ALTER TABLE calls ADD COLUMN Cancelled BOOLEAN;")
            except sqlite3.OperationalError: pass

    def check_if_updated(self):
        """
        Polled every 10 seconds by the Tkinter UI to check if another computer changed the DB.
        Uses MAX(HistoryID) because it is immune to row deletions and race conditions.
        """
        try:
            self.conn.commit() # Forces SQLite to clear cache and check the actual file
            cursor = self.conn.execute("SELECT MAX(HistoryID) FROM call_history")
            result = cursor.fetchone()[0]
            return result if result else 0
        except Exception:
            return -1

    def _log_history(self, call_id, user, action, details=""):
        """Internal helper to write to the uneditable liability audit log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO call_history (CallID, Timestamp, User, Action, Details) VALUES (?, ?, ?, ?, ?)",
            (call_id, timestamp, user, action, details)
        )

    def get_all_calls(self, sort_by="ReportID", sort_order="ASC", active_only=False):
        valid_columns = ["ReportID", "CallDate", "Location", "Code", "ResolutionStatus", "Cancelled"]
        if sort_by not in valid_columns: sort_by = "ReportID"
        sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
        
        query = "SELECT * FROM calls WHERE (Deleted = 0 OR Deleted IS NULL)"
        if active_only:
            query += " AND (ResolutionStatus = 0 OR ResolutionStatus IS NULL) AND (Cancelled = 0 OR Cancelled IS NULL)"
            
        query += f" ORDER BY {sort_by} {sort_order}"
        cursor = self.conn.execute(query)
        return cursor.fetchall()

    def get_call_by_id(self, report_id):
        cursor = self.conn.execute("SELECT * FROM calls WHERE ReportID = ?", (report_id,))
        return cursor.fetchone()

    def get_history_for_call(self, report_id):
        cursor = self.conn.execute("SELECT * FROM call_history WHERE CallID = ? ORDER BY Timestamp DESC", (report_id,))
        return cursor.fetchall()

    def get_full_audit_log(self):
        """For Admin CSV Export only."""
        cursor = self.conn.execute("SELECT * FROM call_history ORDER BY HistoryID ASC")
        return cursor.fetchall()

    def get_passdown_notes(self):
        cursor = self.conn.execute("SELECT * FROM passdown_notes ORDER BY Timestamp DESC LIMIT 50")
        return cursor.fetchall()

    @sqlite_retry()
    def add_passdown_note(self, user, note):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            self.conn.execute("INSERT INTO passdown_notes (Timestamp, User, Note) VALUES (?, ?, ?)", (timestamp, user, note))

    @sqlite_retry()
    def add_call(self, call, current_user):
        """Creates a new incident and assigns a formatted DC-#### ID."""
        now = datetime.now()
        with self.conn: 
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO calls (
                    CallDate, CallTime, AnsweredTimestamp, AnsweredStatus, AnsweredBy,
                    ResolutionTimestamp, ResolutionStatus, ResolvedBy, InputMedium, Source, 
                    Caller, Location, Code, Description, CreatedBy, ModifiedBy, RedFlag,
                    ReportNumber, Deleted, Cancelled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "", False, "", "", False, "",
                call['InputMedium'], call['Source'], call['Caller'], call['Location'],
                call['Code'], call['Description'], current_user, "", False, "", False, call.get('Cancelled', False)
            ))
            new_id = cursor.lastrowid
            report_id = f"{self.call_id_prefix}-{new_id:04d}"
            cursor.execute("UPDATE calls SET ReportID = ? WHERE ID = ?", (report_id, new_id))
            self._log_history(report_id, current_user, "Call Created")
        return report_id

    @sqlite_retry()
    def modify_call(self, report_id, updated_call, current_user):
        """Updates a call and automatically logs exactly which fields the dispatcher changed."""
        original_call_row = self.get_call_by_id(report_id)
        if not original_call_row: raise ValueError("Call not found.")
        
        original_call = dict(original_call_row)
        modification_details = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Track what changed for the audit log
        for field in ['InputMedium', 'Source', 'Caller', 'Location', 'Code', 'Cancelled']:
            if str(original_call.get(field, '')) != str(updated_call.get(field, '')):
                modification_details.append(f"{field} updated.")
        
        if original_call['Description'].strip() != updated_call['Description'].strip():
            modification_details.append("Description was updated.")

        is_newly_resolved = updated_call["ResolutionStatus"] and not original_call["ResolutionStatus"]
        if is_newly_resolved:
            updated_call["ResolutionTimestamp"] = now
            self._log_history(report_id, current_user, "Call Resolved", f"Resolved by: {updated_call['ResolvedBy']}")
        else:
            if not updated_call["ResolutionStatus"] and original_call["ResolutionStatus"]:
                updated_call["ResolvedBy"], updated_call["ResolutionTimestamp"] = "", ""

        if modification_details:
            self._log_history(report_id, current_user, "Call Modified", "; ".join(modification_details))
        
        updated_call['ModifiedBy'] = current_user
        
        with self.conn:
            self.conn.execute("""
                UPDATE calls SET
                InputMedium=?, Source=?, Caller=?, Location=?, Code=?, Description=?, Cancelled=?,
                ResolutionStatus=?, ResolvedBy=?, ResolutionTimestamp=?, ModifiedBy=?
                WHERE ReportID=?
            """, (
                updated_call['InputMedium'], updated_call['Source'], updated_call['Caller'],
                updated_call['Location'], updated_call['Code'], updated_call['Description'], updated_call.get('Cancelled', False),
                updated_call['ResolutionStatus'], updated_call['ResolvedBy'], 
                updated_call.get('ResolutionTimestamp', original_call['ResolutionTimestamp']),
                updated_call['ModifiedBy'], report_id
            ))
        return True

    def create_backup(self, backup_dir, max_backups):
        """Simple localized SQLite copy function."""
        if not os.path.exists(backup_dir): os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = os.path.join(backup_dir, f"backup_{timestamp}.db")
        try:
            b_conn = sqlite3.connect(backup_filename)
            with b_conn: self.conn.backup(b_conn, pages=1, progress=None)
            b_conn.close()
            backup_files = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")], key=os.path.getmtime)
            while len(backup_files) > max_backups: os.remove(backup_files.pop(0))
            return f"Backup created: {os.path.basename(backup_filename)}"
        except Exception as e:
            raise Exception(f"Failed to create backup: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None