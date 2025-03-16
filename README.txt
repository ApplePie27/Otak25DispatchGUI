Dispatch Call Management System

Overview
The Dispatch Call Management System is a Python-based application designed to help users efficiently manage dispatch calls. It provides a user-friendly interface for adding, resolving, modifying, and deleting calls, as well as saving and loading data in .txt or .csv formats. The system includes features such as autosaving, logging, a search bar, and the ability to filter calls by status.

Features
- Add New Calls: Add calls with details like Call ID, Call Date, Call Time, Input Medium, Source, Caller, Location, Code, and Description.
- Resolve Calls: Mark calls as resolved and specify who resolved them.
- Modify Calls: Update existing call details.
- Delete Calls: Remove calls from the system.
- Save and Load Data: Save data to .txt or .csv files and load it back.
- Autosave: Automatically save data to autosave.txt and autosave.csv.
- Search Bar: Filter calls by Call ID, Caller, or Description.
- Filter by Status: Show only resolved or unresolved calls.
- Print Report: Generate a report of all calls.

System Requirements
- Operating System: Windows, macOS, or Linux.
- Python Version: Python 3.x.
- Dependencies: Tkinter (included with Python), csv, json, hashlib, datetime.

Installation
1. Ensure Python 3.x is installed on your system.
2. Download the source code for the Dispatch Call Management System.
3. Extract the files to a directory of your choice.

How to Run
1. Open a terminal or command prompt.
2. Navigate to the directory containing the source code.
3. Run the following command:
   python main.py

User Guide
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

Filtering Calls
1. Use the search bar to filter calls by Call ID, Caller, or Description.
2. Use the "Filter by Status" dropdown to show only resolved or unresolved calls.

Printing a Report
1. Click "Print Report".
2. Choose a location to save the report.
3. The report will be generated and saved as a .txt file.

Saving and Loading Data
- Save Data: Click "Save" in the File menu to save data to a .txt or .csv file.
- Load Data: Click "Load" in the File menu to load data from a .txt or .csv file.

Troubleshooting
- File Not Found Error: Ensure autosave.txt or autosave.csv exists in the same directory as the application.
- Input Validation Errors: Ensure all required fields are filled before adding or modifying a call.
- Data Corruption: Avoid manually editing autosave.txt or autosave.csv files.
- Performance Issues: Large datasets may slow down the application. Consider splitting data into smaller files.

Pros and Cons
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