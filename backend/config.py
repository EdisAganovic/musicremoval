"""
Configuration and shared state for the backend.

This module is the single import surface every route/service in this backend
actually uses (`from config import ...`) - the implementation lives in
core.constants / core.state / utils.* / services.persistence / services.cleanup,
and this file just re-exports it in one place. Add new re-exports here when you
add a new shared helper in one of those modules; don't import from the
specialized modules directly, since nothing else in the codebase does that and
it would just fragment the import style.
"""

# Re-export from core.constants
from core.constants import (
    LIBRARY_FILE,
    QUEUE_FILE,
    NOTIFICATIONS_FILE,
    METADATA_CACHE_FILE,
    TASKS_FILE,
    MAX_LOGS,
    MAX_NOTIFICATIONS,
)

# Re-export from core.state
from core.state import (
    tasks,
    download_queue,
    notifications,
    active_downloads,
    metadata_cache,
    console_logs,
    tasks_lock,
    download_queue_lock,
    notifications_lock,
    active_downloads_lock,
    metadata_cache_lock,
    console_logs_lock,
    queue_lock,
    queue_processing,
    random_delay_enabled,
)

# Re-export from utils.file_ops
from utils.file_ops import (
    safe_remove,
    safe_makedirs,
    safe_file_copy,
    safe_file_move,
    safe_file_exists,
    safe_get_file_size,
)

# Re-export from utils.validation
from utils.validation import (
    safe_path,
    validate_url,
    validate_youtube_url,
    is_youtube_url,
    sanitize_filename,
)

# Re-export from utils.async_tools
from utils.async_tools import (
    TransactionContext,
    backup_file,
    restore_from_backup,
    cleanup_backup,
    run_with_timeout,
    run_sync_with_timeout,
)

# Re-export from services.persistence
from services.persistence import (
    init_data_directory,
    load_tasks_async,
    save_tasks_async,
    save_tasks_sync,
    get_task_async,
    set_task_async,
    update_task_async,
    delete_task_async,
    get_all_tasks_async,
    get_active_downloads_async,
    set_active_download_async,
    delete_active_download_async,
    save_to_library,
    get_full_library,
    load_queue,
    load_queue_async,
    save_queue_async,
    save_queue,
    load_notifications_async,
    load_notifications,
    save_notifications_async,
    save_notifications,
    add_notification_async,
    add_notification,
    load_metadata_cache_async,
    load_metadata_cache,
    save_metadata_cache_async,
    save_metadata_cache,
    log_console_async,
    log_console,
    get_file_metadata_cached,
)

# Re-export from services.cleanup
from services.cleanup import (
    cleanup_completed_tasks,
    cleanup_metadata_cache,
    cleanup_temp_files,
    periodic_cleanup,
    start_cleanup_scheduler,
    stop_cleanup_scheduler,
)

__all__ = [
    # constants
    "LIBRARY_FILE",
    "QUEUE_FILE",
    "NOTIFICATIONS_FILE",
    "METADATA_CACHE_FILE",
    "TASKS_FILE",
    "MAX_LOGS",
    "MAX_NOTIFICATIONS",
    # state
    "tasks",
    "download_queue",
    "notifications",
    "active_downloads",
    "metadata_cache",
    "console_logs",
    "tasks_lock",
    "download_queue_lock",
    "notifications_lock",
    "active_downloads_lock",
    "metadata_cache_lock",
    "console_logs_lock",
    "queue_lock",
    "queue_processing",
    "random_delay_enabled",
    # file_ops
    "safe_remove",
    "safe_makedirs",
    "safe_file_copy",
    "safe_file_move",
    "safe_file_exists",
    "safe_get_file_size",
    # validation
    "safe_path",
    "validate_url",
    "validate_youtube_url",
    "is_youtube_url",
    "sanitize_filename",
    # async_tools
    "TransactionContext",
    "backup_file",
    "restore_from_backup",
    "cleanup_backup",
    "run_with_timeout",
    "run_sync_with_timeout",
    # persistence
    "init_data_directory",
    "load_tasks_async",
    "save_tasks_async",
    "save_tasks_sync",
    "get_task_async",
    "set_task_async",
    "update_task_async",
    "delete_task_async",
    "get_all_tasks_async",
    "get_active_downloads_async",
    "set_active_download_async",
    "delete_active_download_async",
    "save_to_library",
    "get_full_library",
    "load_queue",
    "load_queue_async",
    "save_queue_async",
    "save_queue",
    "load_notifications_async",
    "load_notifications",
    "save_notifications_async",
    "save_notifications",
    "add_notification_async",
    "add_notification",
    "load_metadata_cache_async",
    "load_metadata_cache",
    "save_metadata_cache_async",
    "save_metadata_cache",
    "log_console_async",
    "log_console",
    "get_file_metadata_cached",
    # cleanup
    "cleanup_completed_tasks",
    "cleanup_metadata_cache",
    "cleanup_temp_files",
    "periodic_cleanup",
    "start_cleanup_scheduler",
    "stop_cleanup_scheduler",
]