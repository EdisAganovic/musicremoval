"""
Queue service - handles download queue processing.
"""
import asyncio
import random
import uuid
from colorama import Fore, Style

from config import queue_processing, download_queue, save_queue, tasks
from services.download_service import run_yt_dlp


async def process_queue():
    """Process download queue items one by one."""
    global queue_processing, download_queue

    if queue_processing:
        return

    queue_processing = True

    while True:
        pending_item = None
        for item in download_queue:
            if item.get("status") == "pending":
                pending_item = item
                break

        if not pending_item:
            break

        pending_item["status"] = "downloading"
        save_queue()

        task_id = str(uuid.uuid4())
        pending_item["task_id"] = task_id

        await asyncio.to_thread(
            run_yt_dlp,
            task_id,
            pending_item["url"],
            pending_item.get("format_type", "audio"),
            pending_item.get("format_id"),
            None,
            pending_item.get("auto_separate", False),
            pending_item.get("subfolder")
        )

        task_status = tasks.get(task_id, {})
        if task_status.get("status") == "completed":
            pending_item["status"] = "completed"
        else:
            pending_item["status"] = "failed"

        save_queue()

        delay = random.randint(3, 7)
        print(f"{Fore.YELLOW}Waiting {delay} seconds before next download...{Style.RESET_ALL}")
        await asyncio.sleep(delay)

    queue_processing = False
