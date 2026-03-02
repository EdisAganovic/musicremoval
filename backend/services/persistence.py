"""
JSON data loading and saving logic for persistence.
"""
import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from colorama import Fore, Style

from core.constants import (
    LIBRARY_FILE, QUEUE_FILE, NOTIFICATIONS_FILE, 
    METADATA_CACHE_FILE, TASKS_FILE, MAX_LOGS, MAX_NOTIFICATIONS
)
from core.state import (
    tasks, tasks_lock, download_queue, download_queue_lock,
    notifications, notifications_lock, metadata_cache, metadata_cache_lock,
    console_logs, console_logs_lock, active_downloads, active_downloads_lock
)
from utils.file_ops import safe_makedirs


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


# ============== Task State Persistence ==============

async def load_tasks_async():
    """Load tasks from disk on startup."""
    global tasks
    async with tasks_lock:
        if os.path.exists(TASKS_FILE) and os.path.getsize(TASKS_FILE) > 0:
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    loaded_tasks = json.load(f)
                
                # Merge with current tasks if any exist (usually empty on startup)
                # Only load incomplete tasks (not completed/failed/cancelled)
                # OR recently completed tasks (last 5 minutes)
                now = time.time()
                active_tasks = {}
                for k, v in loaded_tasks.items():
                    status = v.get("status")
                    if status not in ["completed", "failed", "cancelled"]:
                        active_tasks[k] = v
                    elif v.get("created_at", 0) > now - 3600: # Keep recent for UI
                        active_tasks[k] = v
                
                tasks.update(active_tasks)
                print(f"{Fore.CYAN}Loaded {len(active_tasks)} tasks from persistence{Style.RESET_ALL}")
            except (json.JSONDecodeError, OSError, IOError) as e:
                print(f"{Fore.YELLOW}Warning: Could not load tasks: {e}{Style.RESET_ALL}")
        # If file doesn't exist, we just start with empty tasks (already initialized)


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
            # If status changed to completed/failed, ensure it's saved
            await _save_tasks_internal()
        else:
            # If task doesn't exist, create it if it has enough info
            if "status" in updates:
                tasks[task_id] = updates
                await _save_tasks_internal()

async def _save_tasks_internal():
    """Save tasks to disk - internal helper without lock (assumes caller has it)."""
    try:
        # Create a copy to avoid mutation during save
        tasks_copy = dict(tasks)
        # Filter to only save persistent-worthy tasks (exclude very transient data if needed)
        # But for now, save all.
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks_copy, f, indent=4)
    except (OSError, IOError, TypeError) as e:
        print(f"Error saving tasks: {e}")

async def delete_task_async(task_id: str):
    """Delete task with lock protection and persistence."""
    async with tasks_lock:
        tasks.pop(task_id, None)
        await _save_tasks_internal()


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
                loaded = json.load(f)
                download_queue.clear()
                download_queue.extend(loaded)
        except (json.JSONDecodeError, OSError, IOError):
            download_queue.clear()


async def load_queue_async():
    """Loads the download queue from disk with lock protection."""
    global download_queue
    async with download_queue_lock:
        if os.path.exists(QUEUE_FILE) and os.path.getsize(QUEUE_FILE) > 0:
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    download_queue.clear()
                    download_queue.extend(loaded)
            except (json.JSONDecodeError, OSError, IOError):
                download_queue.clear()


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
                    loaded = json.load(f)
                    notifications.clear()
                    notifications.extend(loaded)
            except (json.JSONDecodeError, OSError, IOError):
                notifications.clear()


def load_notifications():
    """Loads notifications from disk."""
    global notifications
    if os.path.exists(NOTIFICATIONS_FILE) and os.path.getsize(NOTIFICATIONS_FILE) > 0:
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                notifications.clear()
                notifications.extend(loaded)
        except (json.JSONDecodeError, OSError, IOError):
            notifications.clear()


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
        # Trim to max notifications
        while len(notifications) > MAX_NOTIFICATIONS:
            notifications.pop()
    await save_notifications_async()
    print(f"[NOTIFICATION] {type.upper()}: {title} - {message}")


def add_notification(type: str, title: str, message: str, data: dict = None):
    """Adds a new notification."""
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
    # Trim to max notifications
    while len(notifications) > MAX_NOTIFICATIONS:
        notifications.pop()
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
                    loaded = json.load(f)
                    metadata_cache.clear()
                    metadata_cache.update(loaded)
                print(f"{Fore.CYAN}Loaded metadata cache with {len(metadata_cache)} entries{Style.RESET_ALL}")
            except (json.JSONDecodeError, OSError, IOError):
                metadata_cache.clear()
        else:
            metadata_cache.clear()


def load_metadata_cache():
    """Loads metadata cache from disk."""
    global metadata_cache
    if os.path.exists(METADATA_CACHE_FILE) and os.path.getsize(METADATA_CACHE_FILE) > 0:
        try:
            with open(METADATA_CACHE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                metadata_cache.clear()
                metadata_cache.update(loaded)
            print(f"{Fore.CYAN}Loaded metadata cache with {len(metadata_cache)} entries{Style.RESET_ALL}")
        except (json.JSONDecodeError, OSError, IOError):
            metadata_cache.clear()
    else:
        metadata_cache.clear()


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
    console_logs.append({
        "message": message,
        "level": level,
        "time": datetime.now().isoformat()
    })
    if len(console_logs) > MAX_LOGS:
        console_logs.pop(0)
    print(message)


# ============== File Metadata Cache Helper ==============

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