"""
Configuration and shared state for the backend.
"""
import os
import json
import asyncio
from typing import Dict, List, Optional
from colorama import Fore, Style

# File paths
LIBRARY_FILE = "data/library.json"
QUEUE_FILE = "data/download_queue.json"
NOTIFICATIONS_FILE = "data/notifications.json"
METADATA_CACHE_FILE = "data/metadata_cache.json"

# Shared state
tasks: Dict[str, dict] = {}  # task_id -> task data
download_queue: List[dict] = []  # Queue items
notifications: List[dict] = []  # Notifications
active_downloads: Dict[str, dict] = {}  # task_id -> { "cancel_flag": bool, "ydl": instance }
metadata_cache: Dict[str, dict] = {}  # file metadata cache
console_logs: List[dict] = []  # Console logs for frontend

# State persistence
TASKS_FILE = "data/tasks.json"

# Settings
MAX_LOGS = 500
MAX_NOTIFICATIONS = 50

# Locks for thread-safe access to shared global state
tasks_lock = asyncio.Lock()
download_queue_lock = asyncio.Lock()
notifications_lock = asyncio.Lock()
active_downloads_lock = asyncio.Lock()
metadata_cache_lock = asyncio.Lock()
console_logs_lock = asyncio.Lock()

# Queue processing state
queue_lock = asyncio.Lock()
queue_processing = False


# ============== Thread-Safe Task Management Helpers ==============

async def get_task_async(task_id: str):
    """Get task by ID with lock protection."""
    async with tasks_lock:
        return tasks.get(task_id)


async def set_task_async(task_id: str, task_data: dict):
    """Set task with lock protection and persistence."""
    async with tasks_lock:
        tasks[task_id] = task_data
    await save_tasks_async()


async def update_task_async(task_id: str, updates: dict):
    """Update task fields with lock protection and persistence."""
    async with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(updates)
    await save_tasks_async()


async def delete_task_async(task_id: str):
    """Delete task with lock protection and persistence."""
    async with tasks_lock:
        tasks.pop(task_id, None)
    await save_tasks_async()


async def get_all_tasks_async():
    """Get all tasks with lock protection."""
    async with tasks_lock:
        return dict(tasks)


async def get_active_downloads_async():
    """Get active downloads with lock protection."""
    async with active_downloads_lock:
        return dict(active_downloads)


async def set_active_download_async(task_id: str, download_data: dict):
    """Set active download with lock protection."""
    async with active_downloads_lock:
        active_downloads[task_id] = download_data


async def delete_active_download_async(task_id: str):
    """Delete active download with lock protection."""
    async with active_downloads_lock:
        active_downloads.pop(task_id, None)


# ============== Safe File Operations ==============

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
    import shutil
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
    import shutil
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


# ============== Input Validation ==============

def safe_path(user_input: str, base_dir: str) -> Optional[str]:
    """
    Validate and sanitize file paths to prevent path traversal attacks.
    Returns resolved absolute path if valid, None otherwise.
    """
    try:
        from pathlib import Path
        resolved = Path(base_dir).resolve()
        target = (resolved / user_input).resolve()
        if str(target).startswith(str(resolved)):
            return str(target)
    except (ValueError, TypeError, OSError):
        pass
    return None


def validate_url(url: str) -> bool:
    """
    Basic URL validation.
    Returns True if URL appears valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False
    # Basic URL pattern check
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    # Check for obviously malicious patterns
    dangerous_patterns = ['javascript:', 'data:', 'file:', 'vbscript:']
    if any(pattern in url.lower() for pattern in dangerous_patterns):
        return False
    return True


def validate_youtube_url(url: str) -> bool:
    """
    Validate YouTube URL format.
    Returns True if URL appears to be a valid YouTube URL.
    """
    if not validate_url(url):
        return False
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'www.youtu.be']
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc in youtube_domains:
            return True
    except (ImportError, ValueError):
        pass
    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing or replacing invalid characters.
    Returns sanitized filename.
    """
    if not filename or not isinstance(filename, str):
        return "unnamed"
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    # Limit length
    return filename[:255]


# ============== Data Directory Initialization ==============

def init_data_directory():
    """
    Ensure data directory exists and all required JSON files are initialized.
    Should be called on app startup.
    """
    data_dir = "data"
    safe_makedirs(data_dir, exist_ok=True)
    
    required_files = {
        "library.json": [],
        "download_queue.json": [],
        "notifications.json": [],
        "metadata_cache.json": {},
        "tasks.json": {}
    }
    
    for filename, default_content in required_files.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=4)
                print(f"{Fore.GREEN}Created {filepath}{Style.RESET_ALL}")
            except (OSError, IOError, TypeError) as e:
                print(f"{Fore.RED}Error creating {filepath}: {e}{Style.RESET_ALL}")
    
    # Also create video.json with default settings if missing
    video_config_path = os.path.join(data_dir, "video.json")
    if not os.path.exists(video_config_path):
        default_video_config = {
            "presets": {
                "fast": {
                    "label": "Fast (Small Size)",
                    "video": {"codec": "libx264", "bitrate": "1000k"},
                    "audio": {"codec": "aac", "bitrate": "128k"}
                },
                "balanced": {
                    "label": "Balanced (Recommended)",
                    "video": {"codec": "libx264", "bitrate": "1800k"},
                    "audio": {"codec": "aac", "bitrate": "192k"}
                },
                "quality": {
                    "label": "High Quality (Large Size)",
                    "video": {"codec": "libx264", "bitrate": "3000k"},
                    "audio": {"codec": "aac", "bitrate": "256k"}
                }
            },
            "current_preset": "balanced",
            "video": {"codec": "copy", "bitrate": None},
            "audio": {"codec": "aac", "bitrate": "192k"},
            "output": {"format": "mp4"},
            "processing": {"demucs_workers": 2}
        }
        try:
            with open(video_config_path, 'w', encoding='utf-8') as f:
                json.dump(default_video_config, f, indent=4)
            print(f"{Fore.GREEN}Created {video_config_path}{Style.RESET_ALL}")
        except (OSError, IOError, TypeError) as e:
            print(f"{Fore.RED}Error creating {video_config_path}: {e}{Style.RESET_ALL}")


# ============== Transactional Operations with Rollback ==============

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
    if not os.path.exists(filepath):
        return None
    try:
        import shutil
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
    if not backup_path or not os.path.exists(backup_path):
        return False
    try:
        import shutil
        shutil.copy2(backup_path, original_path)
        return True
    except (OSError, IOError, shutil.Error):
        return False


def cleanup_backup(backup_path: str) -> bool:
    """
    Remove backup file.
    Returns True if successful or backup doesn't exist, False on error.
    """
    if backup_path and os.path.exists(backup_path):
        return safe_remove(backup_path)
    return True


# ============== Timeout Helpers ==============

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
    import concurrent.futures
    
    def wrapper():
        return func(*args, **kwargs)
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(wrapper)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"{operation_name} timed out after {timeout}s")


# ============== Task State Persistence ==============

async def load_tasks_async():
    """Load tasks from disk on startup."""
    global tasks
    async with tasks_lock:
        if os.path.exists(TASKS_FILE) and os.path.getsize(TASKS_FILE) > 0:
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    loaded_tasks = json.load(f)
                # Only load incomplete tasks (not completed/failed/cancelled)
                active_tasks = {
                    k: v for k, v in loaded_tasks.items()
                    if v.get("status") not in ["completed", "failed", "cancelled"]
                }
                tasks = active_tasks
                print(f"{Fore.CYAN}Loaded {len(tasks)} active tasks from persistence{Style.RESET_ALL}")
            except (json.JSONDecodeError, OSError, IOError) as e:
                print(f"{Fore.YELLOW}Warning: Could not load tasks: {e}{Style.RESET_ALL}")
                tasks = {}
        else:
            tasks = {}


async def save_tasks_async():
    """Save tasks to disk."""
    async with tasks_lock:
        try:
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=4)
        except (OSError, IOError, TypeError) as e:
            print(f"Error saving tasks: {e}")


def save_tasks_sync():
    """Save tasks to disk (sync version)."""
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving tasks: {e}")


async def cleanup_completed_tasks():
    """Remove completed/failed/cancelled tasks older than 24 hours."""
    import time
    async with tasks_lock:
        current_time = time.time()
        stale_ids = []
        
        for task_id, task_data in tasks.items():
            status = task_data.get("status")
            created_at = task_data.get("created_at", current_time)
            
            # Remove tasks that are completed/failed/cancelled and older than 24h
            if status in ["completed", "failed", "cancelled"]:
                if current_time - created_at > 24 * 60 * 60:
                    stale_ids.append(task_id)
        
        for task_id in stale_ids:
            tasks.pop(task_id, None)
        
        if stale_ids:
            print(f"{Fore.CYAN}Cleaned up {len(stale_ids)} completed tasks{Style.RESET_ALL}")
            # Save after cleanup
            try:
                with open(TASKS_FILE, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, indent=4)
            except (OSError, IOError, TypeError):
                pass


# ============== Background Cleanup Scheduler ==============

_cleanup_task = None
_cleanup_interval_seconds = 3600  # 1 hour


async def periodic_cleanup():
    """
    Background task that periodically cleans up temp files and old data.
    Runs every hour by default.
    """
    import time
    
    while True:
        try:
            await asyncio.sleep(_cleanup_interval_seconds)
            
            print(f"\n{Fore.CYAN}=== Running periodic cleanup ==={Style.RESET_ALL}")
            
            # Clean temp files older than 24 hours
            cleanup_temp_files()
            
            # Clean metadata cache
            cleanup_metadata_cache()
            
            # Clean completed tasks older than 24 hours
            await cleanup_completed_tasks()
            
            print(f"{Fore.GREEN}Periodic cleanup completed{Style.RESET_ALL}\n")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"{Fore.RED}Error in periodic cleanup: {e}{Style.RESET_ALL}")


async def start_cleanup_scheduler(interval_seconds: int = 3600):
    """
    Start the background cleanup scheduler.
    
    Args:
        interval_seconds: How often to run cleanup (default: 1 hour)
    """
    global _cleanup_task, _cleanup_interval_seconds
    _cleanup_interval_seconds = interval_seconds
    
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(periodic_cleanup())
        print(f"{Fore.CYAN}Cleanup scheduler started (interval: {interval_seconds}s){Style.RESET_ALL}")


async def stop_cleanup_scheduler():
    """Stop the background cleanup scheduler."""
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        _cleanup_task = None
        print(f"{Fore.CYAN}Cleanup scheduler stopped{Style.RESET_ALL}")


# ============== Library Functions ==============

def save_to_library(task_data):
    """Saves a completed task to the local JSON library."""
    import time
    
    try:
        library = []
        if os.path.exists(LIBRARY_FILE) and os.path.getsize(LIBRARY_FILE) > 0:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                try:
                    library = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: {LIBRARY_FILE} was corrupted. Starting fresh.")
                    library = []

        existing_ids = {t.get("task_id") for t in library if isinstance(t, dict)}
        existing_urls = {t.get("url") for t in library if isinstance(t, dict) and t.get("url")}

        task_id = task_data.get("task_id")
        task_url = task_data.get("url")

        # Add created_at timestamp if not present
        if "created_at" not in task_data:
            task_data["created_at"] = time.time()

        if task_id not in existing_ids and (not task_url or task_url not in existing_urls):
            library.insert(0, task_data)
        elif task_url and task_url in existing_urls:
            for i, item in enumerate(library):
                if item.get("url") == task_url:
                    # Preserve original created_at when updating
                    if item.get("created_at"):
                        task_data["created_at"] = item["created_at"]
                    library[i] = task_data
                    break

        library = library[:500]

        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving to library: {e}")


def get_full_library():
    """Reads all completed tasks and prunes missing files."""
    if not os.path.exists(LIBRARY_FILE) or os.path.getsize(LIBRARY_FILE) == 0:
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            library = json.load(f)

        valid_items = []
        changed = False
        for item in library:
            res_files = item.get("result_files", [])
            if res_files and os.path.exists(res_files[0]):
                valid_items.append(item)
            else:
                changed = True

        if changed:
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(valid_items, f, indent=4)
            return valid_items

        return library
    except (json.JSONDecodeError, OSError, IOError):
        return []


# ============== Queue Functions ==============

def load_queue():
    """Loads the download queue from disk."""
    global download_queue
    if os.path.exists(QUEUE_FILE) and os.path.getsize(QUEUE_FILE) > 0:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                download_queue = json.load(f)
        except (json.JSONDecodeError, OSError, IOError):
            download_queue = []


async def load_queue_async():
    """Loads the download queue from disk with lock protection."""
    global download_queue
    async with download_queue_lock:
        if os.path.exists(QUEUE_FILE) and os.path.getsize(QUEUE_FILE) > 0:
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    download_queue = json.load(f)
            except (json.JSONDecodeError, OSError, IOError):
                download_queue = []


async def save_queue_async():
    """Saves the download queue to disk with lock protection."""
    async with download_queue_lock:
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(download_queue, f, indent=4)
        except (OSError, IOError, TypeError) as e:
            print(f"Error saving queue: {e}")


def save_queue():
    """Saves the download queue to disk."""
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(download_queue, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving queue: {e}")


# ============== Notifications Functions ==============

async def load_notifications_async():
    """Loads notifications from disk with lock protection."""
    global notifications
    async with notifications_lock:
        if os.path.exists(NOTIFICATIONS_FILE) and os.path.getsize(NOTIFICATIONS_FILE) > 0:
            try:
                with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                    notifications = json.load(f)
            except (json.JSONDecodeError, OSError, IOError):
                notifications = []


def load_notifications():
    """Loads notifications from disk."""
    global notifications
    if os.path.exists(NOTIFICATIONS_FILE) and os.path.getsize(NOTIFICATIONS_FILE) > 0:
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)
        except (json.JSONDecodeError, OSError, IOError):
            notifications = []


async def save_notifications_async():
    """Saves notifications to disk with lock protection."""
    async with notifications_lock:
        try:
            with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(notifications, f, indent=4)
        except (OSError, IOError, TypeError) as e:
            print(f"Error saving notifications: {e}")


def save_notifications():
    """Saves notifications to disk."""
    try:
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(notifications, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving notifications: {e}")


async def add_notification_async(type: str, title: str, message: str, data: dict = None):
    """Adds a new notification with lock protection."""
    import time
    import uuid
    async with notifications_lock:
        notification = {
            "id": str(uuid.uuid4()),
            "type": type,
            "title": title,
            "message": message,
            "data": data or {},
            "read": False,
            "created_at": time.time()
        }
        notifications.insert(0, notification)
        notifications[:] = notifications[:MAX_NOTIFICATIONS]
    await save_notifications_async()
    print(f"[NOTIFICATION] {type.upper()}: {title} - {message}")


def add_notification(type: str, title: str, message: str, data: dict = None):
    """Adds a new notification."""
    import time
    import uuid
    notification = {
        "id": str(uuid.uuid4()),
        "type": type,
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": time.time()
    }
    notifications.insert(0, notification)
    notifications[:] = notifications[:MAX_NOTIFICATIONS]
    save_notifications()
    print(f"[NOTIFICATION] {type.upper()}: {title} - {message}")


# ============== Metadata Cache Functions ==============

async def load_metadata_cache_async():
    """Loads metadata cache from disk with lock protection."""
    global metadata_cache
    async with metadata_cache_lock:
        if os.path.exists(METADATA_CACHE_FILE) and os.path.getsize(METADATA_CACHE_FILE) > 0:
            try:
                with open(METADATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    metadata_cache = json.load(f)
                print(f"{Fore.CYAN}Loaded metadata cache with {len(metadata_cache)} entries{Style.RESET_ALL}")
            except (json.JSONDecodeError, OSError, IOError):
                metadata_cache = {}
        else:
            metadata_cache = {}


def load_metadata_cache():
    """Loads metadata cache from disk."""
    global metadata_cache
    if os.path.exists(METADATA_CACHE_FILE) and os.path.getsize(METADATA_CACHE_FILE) > 0:
        try:
            with open(METADATA_CACHE_FILE, "r", encoding="utf-8") as f:
                metadata_cache = json.load(f)
            print(f"{Fore.CYAN}Loaded metadata cache with {len(metadata_cache)} entries{Style.RESET_ALL}")
        except (json.JSONDecodeError, OSError, IOError):
            metadata_cache = {}
    else:
        metadata_cache = {}


async def save_metadata_cache_async():
    """Saves metadata cache to disk with lock protection."""
    async with metadata_cache_lock:
        try:
            with open(METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(metadata_cache, f, indent=4)
        except (OSError, IOError, TypeError) as e:
            print(f"Error saving metadata cache: {e}")


def save_metadata_cache():
    """Saves metadata cache to disk."""
    try:
        with open(METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata_cache, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving metadata cache: {e}")


# ============== Console Log Functions ==============

async def log_console_async(message: str, level: str = "info"):
    """Add message to console logs with lock protection"""
    from datetime import datetime
    async with console_logs_lock:
        console_logs.append({
            "message": message,
            "level": level,
            "time": datetime.now().isoformat()
        })
        if len(console_logs) > MAX_LOGS:
            console_logs.pop(0)
    print(message)


def log_console(message: str, level: str = "info"):
    """Add message to console logs (sync version)"""
    from datetime import datetime
    console_logs.append({
        "message": message,
        "level": level,
        "time": datetime.now().isoformat()
    })
    if len(console_logs) > MAX_LOGS:
        console_logs.pop(0)
    print(message)


def get_file_metadata_cached(file_path):
    """Gets file metadata using cache for fast repeated access."""
    from modules.module_ffmpeg import get_file_metadata

    # Generate hash from file path + modification time for cache key
    try:
        mtime = os.path.getmtime(file_path)
        cache_key = f"{file_path}:{mtime}"
    except (OSError, ValueError):
        cache_key = file_path

    # Check cache first
    if cache_key in metadata_cache:
        return metadata_cache[cache_key]

    # Not in cache, extract metadata
    try:
        metadata = get_file_metadata(file_path)
    except (OSError, IOError, RuntimeError):
        metadata = {"duration": "N/A", "resolution": "N/A", "audio_codec": "N/A", "video_codec": "N/A", "is_video": False}

    # Save to cache
    metadata_cache[cache_key] = metadata

    # Periodically save cache (every 100 entries)
    if len(metadata_cache) % 100 == 0:
        save_metadata_cache()

    return metadata


# ============== Cleanup Functions ==============

def cleanup_metadata_cache():
    """Remove cache entries for files that no longer exist."""
    global metadata_cache
    stale_keys = []

    for cache_key in metadata_cache:
        file_path = cache_key.rsplit(':', 1)[0] if ':' in cache_key else cache_key
        if not os.path.exists(file_path):
            stale_keys.append(cache_key)

    for key in stale_keys:
        del metadata_cache[key]

    if stale_keys:
        print(f"{Fore.CYAN}Cleaned {len(stale_keys)} stale metadata cache entries{Style.RESET_ALL}")
        save_metadata_cache()


def cleanup_temp_files():
    """Clean up temporary files older than 24 hours."""
    import time
    temp_dirs = ['_temp', 'uploads', 'spleeter_out', 'demucs_out', '_processing_intermediates']
    max_age_seconds = 24 * 60 * 60  # 24 hours
    current_time = time.time()
    cleaned_count = 0

    print(f"\n{Fore.CYAN}=== Cleaning up temporary files ==={Style.RESET_ALL}")

    # Cleanup incomplete downloads
    download_dir = os.path.join(os.path.dirname(__file__), '..', 'download')
    if os.path.exists(download_dir):
        orphan_count = 0
        for f in os.listdir(download_dir):
            if f.endswith(('.part', '.ytdl', '.part-Frag')) or '.part-Frag' in f:
                f_path = os.path.join(download_dir, f)
                try:
                    file_age = current_time - os.path.getmtime(f_path)
                    if file_age > 3600:
                        if safe_remove(f_path):
                            orphan_count += 1
                except (OSError, IOError):
                    pass
        if orphan_count > 0:
            print(f"  Cleaned up {orphan_count} orphaned partial downloads")

    for dir_name in temp_dirs:
        dir_path = os.path.join(os.path.dirname(__file__), '..', dir_name)
        if not os.path.exists(dir_path):
            continue

        try:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            if safe_remove(file_path):
                                cleaned_count += 1
                    except (OSError, IOError):
                        pass
        except (OSError, IOError):
            pass

    if cleaned_count > 0:
        print(f"{Fore.GREEN}✓ Cleaned {cleaned_count} old files{Style.RESET_ALL}\n")
    else:
        print(f"  No old files to clean\n")
