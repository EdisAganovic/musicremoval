"""
Async helpers: TransactionContext, timeouts.
"""
import asyncio
import concurrent.futures
import os
from typing import Optional


class TransactionContext:
    """
    Context manager for transactional operations with rollback support.
    
    Usage:
        with TransactionContext() as tx:
            tx.add_action(lambda: os.remove(file1))
            tx.add_action(lambda: os.remove(file2))
            # If any action fails, all completed actions are rolled back
    """
    def __init__(self):
        self.completed_actions = []
        self.rollback_actions = []
        self.success = True

    def add_action(self, action, rollback=None):
        """Add an action with optional rollback."""
        self.completed_actions.append((action, rollback))

    def commit(self):
        """Mark transaction as successful."""
        self.success = True

    def rollback(self):
        """Execute rollback actions in reverse order."""
        for action, rollback in reversed(self.completed_actions):
            if rollback:
                try:
                    rollback()
                except Exception as e:
                    print(f"Warning: Rollback failed: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
            self.rollback()
        return False  # Don't suppress exceptions


def backup_file(filepath: str) -> Optional[str]:
    """
    Create a backup of a file.
    Returns backup path if successful, None otherwise.
    """
    import shutil
    
    if not os.path.exists(filepath):
        return None
    try:
        backup_path = filepath + '.backup'
        shutil.copy2(filepath, backup_path)
        return backup_path
    except (OSError, IOError, shutil.Error):
        return None


def restore_from_backup(backup_path: str, original_path: str) -> bool:
    """
    Restore file from backup.
    Returns True if successful, False otherwise.
    """
    import shutil
    
    if not backup_path or not os.path.exists(backup_path):
        return False
    try:
        shutil.copy2(backup_path, original_path)
        return True
    except (OSError, IOError, shutil.Error):
        return False


def cleanup_backup(backup_path: str) -> bool:
    """
    Remove backup file.
    Returns True if successful or backup doesn't exist, False on error.
    """
    from .file_ops import safe_remove
    
    if backup_path and os.path.exists(backup_path):
        return safe_remove(backup_path)
    return True


async def run_with_timeout(coro, timeout: float, operation_name: str = "Operation"):
    """
    Run an async coroutine with timeout.
    Raises asyncio.TimeoutError if operation exceeds timeout.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"{operation_name} timed out after {timeout}s")


def run_sync_with_timeout(func, timeout: float, operation_name: str = "Operation", *args, **kwargs):
    """
    Run a sync function with timeout using executor.
    Raises TimeoutError if operation exceeds timeout.
    """
    def wrapper():
        return func(*args, **kwargs)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(wrapper)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"{operation_name} timed out after {timeout}s")