# Dispatch Call Management System

This is a Python-based application for managing dispatch calls. It allows users to add, resolve, modify, undo, and redo calls. The system supports saving and loading data in `.txt` and `.csv` formats.

## Features
- Add new calls with details like Call ID, Call Date, Call Time, Input Medium, Source, Caller, Location, Code, and Description.
- Resolve calls by marking them as resolved and specifying who resolved them.
- Modify existing calls.
- Undo and redo actions.
- Save and load data in `.txt` and `.csv` formats.
- Autosave functionality to `autosave.txt` and `autosave.csv`.

## How to Run
1. Install Python 3.x.
2. Run `main.py` to start the application.

## Testing
Run the unit tests using:
```bash
python -m unittest tests/test_dispatch_call_manager.py

---

### Summary:
- **Modularization**: The code is now split into multiple files for better organization.
- **Error Handling**: Improved error handling with user-friendly messages.
- **Documentation**: Added docstrings and a `README.md` file.
- **Testing**: Added unit tests for the `DispatchCallManager` class.
- **Performance**: Optimized file handling and reload logic.

This structure makes the codebase easier to maintain, test, and extend.