import tkinter as tk
from gui import DispatchCallApp
from data_manager import DataManager
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import configparser

def setup_logging():
    """Configure file-based logging for the application."""
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, "dispatch.log")
        
        logger = logging.getLogger('DispatchApp')
        logger.setLevel(logging.INFO)

        if logger.hasHandlers():
            logger.handlers.clear()

        handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
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
        db_file = config.get('DATABASE', 'filename', fallback='dispatch.db')
        
        data_manager = DataManager(db_file)
        
        root = tk.Tk()
        root.withdraw()
        
        app = DispatchCallApp(root, app_logger, data_manager)
        
        if app.current_user:
            root.mainloop()

    except Exception as e:
        app_logger.critical(f"A critical unhandled exception occurred during application run: {e}", exc_info=True)