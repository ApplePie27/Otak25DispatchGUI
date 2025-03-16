# Dispatch Call Management System

This is a Python-based application for managing dispatch calls. It allows users to add, resolve, modify, and delete calls. The system supports saving and loading data in `.txt` and `.csv` formats, and it includes features like autosaving, logging, and a search bar.

## Features
- **Add New Calls**: Add calls with details like Call ID, Call Date, Call Time, Input Medium, Source, Caller, Location, Code, and Description.
- **Resolve Calls**: Mark calls as resolved and specify who resolved them.
- **Modify Calls**: Update existing call details.
- **Delete Calls**: Remove calls from the system.
- **Save and Load Data**: Save data to `.txt` or `.csv` files and load it back.
- **Autosave**: Automatically save data to `autosave.txt` and `autosave.csv`.
- **Search Bar**: Filter calls by Call ID, Caller, or Description.
- **Filter by Status**: Show only resolved or unresolved calls.
- **Print Report**: Generate a report of all calls.
- **Dark Mode**: Toggle between light and dark themes.
- **User Guide**: Access a user guide from the Help menu.

## How to Run
1. Install Python 3.x.
2. Clone this repository or download the source code.
3. Run `main.py` to start the application.

## Keyboard Shortcuts
- **Ctrl + S**: Save data.
- **Ctrl + L**: Load data.

## Testing
Run the unit tests using:
```bash
python -m unittest tests/test_dispatch_call_manager.py