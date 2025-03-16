import hashlib

def calculate_file_hash(filename):
    """Calculate the hash of a file to detect changes."""
    try:
        with open(filename, "rb") as file:
            file_content = file.read()
            return hashlib.md5(file_content).hexdigest()
    except FileNotFoundError:
        return None  # File does not exist