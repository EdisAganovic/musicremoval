"""
Safe file system operations with error handling.
"""
import os
import shutil


def safe_remove(filepath: str) -> bool:
    """
    Safely remove a file with proper error handling.
    Returns True if file was removed, False otherwise.
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"Warning: Failed to remove {filepath}: {e}")
        return False


def safe_makedirs(dirpath: str, exist_ok: bool = True) -> bool:
    """
    Safely create directory with proper error handling.
    Returns True if directory was created or already exists, False on error.
    """
    try:
        os.makedirs(dirpath, exist_ok=exist_ok)
        return True
    except (PermissionError, OSError) as e:
        print(f"Error: Failed to create directory {dirpath}: {e}")
        return False


def safe_file_copy(src: str, dst: str) -> bool:
    """
    Safely copy a file with proper error handling.
    Returns True if copy was successful, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except (FileNotFoundError, PermissionError, OSError, shutil.Error) as e:
        print(f"Error: Failed to copy {src} to {dst}: {e}")
        return False


def safe_file_move(src: str, dst: str) -> bool:
    """
    Safely move a file with proper error handling.
    Returns True if move was successful, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return True
    except (FileNotFoundError, PermissionError, OSError, shutil.Error) as e:
        print(f"Error: Failed to move {src} to {dst}: {e}")
        return False


def safe_file_exists(filepath: str) -> bool:
    """
    Safely check if file exists with proper error handling.
    Returns True if file exists and is accessible, False otherwise.
    """
    try:
        return os.path.isfile(filepath)
    except (OSError, ValueError):
        return False


def safe_get_file_size(filepath: str) -> int:
    """
    Safely get file size with proper error handling.
    Returns file size in bytes, or 0 on error.
    """
    try:
        return os.path.getsize(filepath)
    except (OSError, FileNotFoundError):
        return 0