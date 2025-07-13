import hashlib
import os
import time

def calculate_file_hash(filename):
    """Calculate the MD5 hash of a file; return None if file doesn't exist."""
    try:
        with open(filename, "rb") as file:
            data = file.read()
            return hashlib.md5(data).hexdigest()
    except FileNotFoundError:
        return None

def get_file_modification_time(filename):
    """Get the last modification time of a file, or 0 if file doesn't exist."""
    try:
        return os.path.getmtime(filename)
    except FileNotFoundError:
        return 0