import hashlib

def calculate_file_hash(filename):
    """Calculate the MD5 hash of a file; return None if file doesn't exist."""
    try:
        with open(filename, "rb") as file:
            data = file.read()
            return hashlib.md5(data).hexdigest()
    except FileNotFoundError:
        return None
