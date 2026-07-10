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
        final_status = task_status.get("status")
        if final_status == "completed":
            pending_item["status"] = "completed"
        elif final_status == "cancelled":
            pending_item["status"] = "cancelled"
        else:
            pending_item["status"] = "failed"

        save_queue()

        # Check if we should stop (user clicked stop while downloading)
        if not state.queue_processing:
            break

        # Random delay between downloads (anti-bot measure)
        if state.random_delay_enabled:
            delay = random.randint(8, 15)
            print(f"{Fore.YELLOW}Waiting {delay} seconds (Random Delay Active) before next download...{Style.RESET_ALL}")
            await asyncio.sleep(delay)
        else:
            # Minimal safety delay even if random is off
            await asyncio.sleep(2)

    state.queue_processing = False

