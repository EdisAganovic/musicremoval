"""
Queue service - handles download queue processing.
"""
import asyncio
import random
import uuid
from colorama import Fore, Style

import core.state as state
from config import save_queue, tasks
from services.download_service import run_yt_dlp


async def process_queue():
    """Process download queue items one by one."""

    # Check via the canonical state module so stop_queue() changes are visible
    if state.queue_processing:
        return

    state.queue_processing = True

    while state.queue_processing:
        # Find next pending item from the canonical list
        pending_item = None
        for item in state.download_queue:
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

        # Check if we should stop (user clicked stop while downloading)
        if not state.queue_processing:
            break

        delay = random.randint(3, 7)
        print(f"{Fore.YELLOW}Waiting {delay} seconds before next download...{Style.RESET_ALL}")
        await asyncio.sleep(delay)

    state.queue_processing = False

