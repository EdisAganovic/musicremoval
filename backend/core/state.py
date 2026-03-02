"""
Global variables and their associated asyncio.Lock objects.
"""
import asyncio
from typing import Dict, List

# Shared state
tasks: Dict[str, dict] = {}  # task_id -> task data
download_queue: List[dict] = []  # Queue items
notifications: List[dict] = []  # Notifications
active_downloads: Dict[str, dict] = {}  # task_id -> { "cancel_flag": bool, "ydl": instance }
metadata_cache: Dict[str, dict] = {}  # file metadata cache
console_logs: List[dict] = []  # Console logs for frontend

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