"""
Global variables and their associated asyncio.Lock objects.

NOTE on locking scope: these are asyncio.Lock objects, which only serialize
concurrent *coroutines* running on the same event loop (e.g. two route
handlers awaiting the same lock). They provide no protection against the
plain background threads this app also uses (download_service/separation_service
run via asyncio.to_thread, and mutate `tasks`/`active_downloads` directly from
that thread without awaiting these locks - they can't, since a worker thread
has no running event loop to await on).

In practice this is safe enough for a single-user local app: CPython's GIL
makes individual dict/list item get/set atomic, so the ...Lock-guarded helpers
in services/persistence.py mainly protect the read-modify-write file I/O
(load/save) sequences from interleaving with themselves, and copy-before-dump
is used when serializing `tasks` from persistence.py to avoid a RuntimeError
if a background thread inserts/removes a key mid-iteration. Do not assume these
locks make cross-thread mutation of `tasks`/`download_queue`/etc. fully atomic.
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

# Locks for serializing concurrent async access (see module docstring for scope/limits)
tasks_lock = asyncio.Lock()
download_queue_lock = asyncio.Lock()
notifications_lock = asyncio.Lock()
active_downloads_lock = asyncio.Lock()
metadata_cache_lock = asyncio.Lock()
console_logs_lock = asyncio.Lock()

# Queue processing state
queue_lock = asyncio.Lock()
queue_processing = False
random_delay_enabled = True # Enabled by default as per request