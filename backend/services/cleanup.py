"""
Periodic background cleanup tasks and scheduler.
"""
import os
import time
import asyncio
from colorama import Fore, Style

from core.constants import TASKS_FILE
from core.state import tasks, tasks_lock, metadata_cache, metadata_cache_lock
from utils.file_ops import safe_remove
from services.persistence import save_metadata_cache


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


async def cleanup_completed_tasks():
    """Remove completed/failed/cancelled tasks older than 24 hours."""
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
            import json
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