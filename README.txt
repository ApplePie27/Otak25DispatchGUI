Dispatch Call Management System
==============================

Overview
--------
The Dispatch Call Management System is a Python-based application for tracking and managing dispatch calls. It features a user-friendly GUI for adding, modifying, resolving, and reporting on calls with automatic data persistence.

Key Features
------------
- Complete call management (add/modify/resolve/delete)
- Dual-format autosaving (TXT and CSV)
- Automated backup system (keeps last 10 versions)
- Comprehensive search and filtering
- Detailed reporting capabilities
- User activity logging
- Red-flag important calls

System Requirements
-------------------
- OS: Windows 10+, macOS 10.15+, or Linux
- Python: 3.8 or later
- RAM: 4GB minimum (8GB recommended)
- Storage: 100MB available space

Installation
------------
1. Ensure Python 3.8+ is installed
2. Download or clone the repository
3. Run from command line:
   python main.py

First Run
---------
- System will create:
  - autosave.txt and autosave.csv
  - backups/ directory
- Prompt for username login

User Guide
----------
Getting Started
1. Logging In: Upon launching the application, enter your username to log in.
2. Main Interface: The main window consists of input fields, buttons, a table for displaying calls, and a log area for system messages.

Adding a New Call
1. Fill in the input fields (Caller, Description, etc.).
2. Click "Add Call" to save the call. The call will appear in the table.

Resolving a Call
1. Select a call from the table.
2. Click "Resolve Call" and enter the name of the resolver.
3. The call will be marked as resolved in the table.

Modifying a Call
1. Select a call from the table.
2. Update the input fields with new details.
3. Click "Modify Call" to update the call in the table.

Deleting a Call
1. Select a call from the table.
2. Click "Delete Call" and confirm the deletion in the dialog box.
3. The call will be removed from the table.

Printing a Report
1. Click "Print Report".
2. Choose a location to save the report.
3. The report will be generated and saved as a .txt file.

Red Flagging a Call
1. Select a call from the table.
2. Click 'Red Flag' to mark the call as important.
3. Red-flagged calls will be highlighted in the table for easy identification.
4. To remove the red flag, select the call and click 'Red Flag' again.

Saving and Loading Data
- Save Data: Click "Save" in the File menu to save data to a .txt or .csv file.
- Load Data: Click "Load" in the File menu to load data from a .txt or .csv file.

Troubleshooting
-------------
- File Not Found Error: Ensure autosave.txt or autosave.csv exists in the same directory as the application.
- Input Validation Errors: Ensure all required fields are filled before adding or modifying a call.
- Data Corruption: Avoid manually editing autosave.txt or autosave.csv files.
- Performance Issues: Large datasets may slow down the application. Consider splitting data into smaller files.

Backup System
-------------
- Automatic backups every 15 minutes
- Stored in backups/ directory
- Files named: BackUp[#]_YYYYMMDD_HHMMSS.ext
- Maintains last 10 backup sets

Pros and Cons
-------------
Pros
- User-Friendly Interface: Intuitive design with clear input fields and buttons.
- Data Persistence: Automatically saves data to prevent loss.
- Customizable: Supports filtering, searching, and reporting.
- Cross-Platform: Works on Windows, macOS, and Linux.

Cons
- Limited Scalability: Designed for small to medium-sized datasets.
- No Database Integration: Uses flat files (.txt and .csv) for data storage.
- Manual Updates: Requires user input for most operations.

License
This project is licensed under the MIT License. See the LICENSE file for details.