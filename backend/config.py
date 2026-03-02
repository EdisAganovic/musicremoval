"""
Configuration and shared state for the backend.
"""
import os
import json
import asyncio
from typing import Dict, List
from colorama import Fore, Style

# File paths
LIBRARY_FILE = "library.json"
QUEUE_FILE = "download_queue.json"
NOTIFICATIONS_FILE = "notifications.json"
METADATA_CACHE_FILE = "metadata_cache.json"

# Shared state
tasks: Dict[str, dict] = {}  # task_id -> task data
download_queue: List[dict] = []  # Queue items
notifications: List[dict] = []  # Notifications
active_downloads: Dict[str, dict] = {}  # task_id -> { "cancel_flag": bool, "ydl": instance }
metadata_cache: Dict[str, dict] = {}  # file metadata cache
console_logs: List[dict] = []  # Console logs for frontend

# Settings
MAX_LOGS = 500
MAX_NOTIFICATIONS = 50

# Queue processing state
queue_lock = asyncio.Lock()
queue_processing = False


# ============== Library Functions ==============

def save_to_library(task_data):
    """Saves a completed task to the local JSON library."""
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

        if task_id not in existing_ids and (not task_url or task_url not in existing_urls):
            library.insert(0, task_data)
        elif task_url and task_url in existing_urls:
            for i, item in enumerate(library):
                if item.get("url") == task_url:
                    library[i] = task_data
                    break

        library = library[:500]

        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=4)
    except Exception as e:
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
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"Error reading library: {e}")
        return []


# ============== Queue Functions ==============

def load_queue():
    """Loads the download queue from disk."""
    global download_queue
    if os.path.exists(QUEUE_FILE) and os.path.getsize(QUEUE_FILE) > 0:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                download_queue = json.load(f)
        except:
            download_queue = []


def save_queue():
    """Saves the download queue to disk."""
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(download_queue, f, indent=4)
    except Exception as e:
        print(f"Error saving queue: {e}")


# ============== Notifications Functions ==============

def load_notifications():
    """Loads notifications from disk."""
    global notifications
    if os.path.exists(NOTIFICATIONS_FILE) and os.path.getsize(NOTIFICATIONS_FILE) > 0:
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)
        except:
            notifications = []


def save_notifications():
    """Saves notifications to disk."""
    try:
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(notifications, f, indent=4)
    except Exception as e:
        print(f"Error saving notifications: {e}")


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

def load_metadata_cache():
    """Loads metadata cache from disk."""
    global metadata_cache
    if os.path.exists(METADATA_CACHE_FILE) and os.path.getsize(METADATA_CACHE_FILE) > 0:
        try:
            with open(METADATA_CACHE_FILE, "r", encoding="utf-8") as f:
                metadata_cache = json.load(f)
            print(f"{Fore.CYAN}Loaded metadata cache with {len(metadata_cache)} entries{Style.RESET_ALL}")
        except:
            metadata_cache = {}
    else:
        metadata_cache = {}


def save_metadata_cache():
    """Saves metadata cache to disk."""
    try:
        with open(METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata_cache, f, indent=4)
    except Exception as e:
        print(f"Error saving metadata cache: {e}")


# ============== Console Log Functions ==============

def log_console(message: str, level: str = "info"):
    """Add message to console logs"""
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
    except:
        cache_key = file_path

    # Check cache first
    if cache_key in metadata_cache:
        return metadata_cache[cache_key]

    # Not in cache, extract metadata
    try:
        metadata = get_file_metadata(file_path)
    except:
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
                        os.remove(f_path)
                        orphan_count += 1
                except:
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
                            os.remove(file_path)
                            cleaned_count += 1
                    except:
                        pass
        except:
            pass

    if cleaned_count > 0:
        print(f"{Fore.GREEN}✓ Cleaned {cleaned_count} old files{Style.RESET_ALL}\n")
    else:
        print(f"  No old files to clean\n")
