"""
MAIN.PY
Entry point for the HQ Dispatch System. 
Initializes background error logging, reads the config, and boots the Tkinter GUI.
"""
import tkinter as tk
from gui import DispatchCallApp
from data_manager import DataManager
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import configparser
import traceback

def setup_logging():
    """Sets up a rotating log file to catch background crashes silently."""
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, "dispatch.log")
        logger = logging.getLogger('DispatchApp')
        logger.setLevel(logging.INFO)

        # Clear old handlers to prevent duplicate logs
        if logger.hasHandlers():
            logger.handlers.clear()

        # Keep the last 5 logs, max 1MB each
        handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        
        return logger
    except Exception as e:
        print(f"FATAL: Could not set up logging. Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    app_logger = setup_logging()
    if not app_logger:
        sys.exit(1)
        
    app_logger.info("Application starting up.")
    
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Load the database path from config.ini (Crucial for Network Drive SMB sharing)
        db_file = config.get('DATABASE', 'filename', fallback='dispatch.db')
        data_manager = DataManager(db_file)
        
        # Hide the blank default Tkinter window, we use our custom one in gui.py
        root = tk.Tk()
        root.withdraw()
        
        # Boot the main application
        app = DispatchCallApp(root, app_logger, data_manager)
        
        # Only start the main UI loop if the user successfully logged in
        if app.current_user:
            root.mainloop()

    except Exception as e:
        # LOUD CRASH CATCHER: If Tkinter fails to boot, freeze the terminal and print exactly why.
        print("\n" + "!"*50)
        print("🚨 CRITICAL UI CRASH DETECTED 🚨")
        print("!"*50)
        traceback.print_exc()
        print("!"*50)
        app_logger.critical(f"Unhandled exception: {e}", exc_info=True)
        input("Press Enter to close this window...")