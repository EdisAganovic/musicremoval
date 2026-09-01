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
        print(f"{Fore.YELLOW}[Queue] process_queue() invoked but queue is already active (state.queue_processing is True).{Style.RESET_ALL}")
        return

    state.queue_processing = True
    print(f"{Fore.CYAN}[Queue] Starting queue processing loop...{Style.RESET_ALL}")

    try:
        while state.queue_processing:
            # Find next pending item from the canonical list
            pending_item = None
            for item in state.download_queue:
                if item.get("status") == "pending":
                    pending_item = item
                    break

            if not pending_item:
                print(f"{Fore.CYAN}[Queue] No pending items in queue.{Style.RESET_ALL}")
                break

            print(f"{Fore.GREEN}[Queue] Processing item: {pending_item.get('title')} ({pending_item.get('url')}){Style.RESET_ALL}")
            pending_item["status"] = "downloading"
            save_queue()

            task_id = str(uuid.uuid4())
            pending_item["task_id"] = task_id

            try:
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
                    pending_item["result_files"] = task_status.get("result_files", [])
                    print(f"{Fore.GREEN}[Queue] Item finished successfully: {pending_item.get('title')}{Style.RESET_ALL}")
                elif final_status == "cancelled":
                    pending_item["status"] = "cancelled"
                    print(f"{Fore.YELLOW}[Queue] Item cancelled: {pending_item.get('title')}{Style.RESET_ALL}")
                else:
                    pending_item["status"] = "failed"
                    print(f"{Fore.RED}[Queue] Item failed: {pending_item.get('title')}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[Queue] Error processing item {task_id}: {e}{Style.RESET_ALL}")
                pending_item["status"] = "failed"
            finally:
                save_queue()

            has_more_pending = any(i.get("status") == "pending" for i in state.download_queue)
            if not has_more_pending:
                print(f"{Fore.GREEN}[Queue] All queue items have finished processing.{Style.RESET_ALL}")
                break

            # Random delay between downloads (anti-bot measure)
            if state.random_delay_enabled:
                delay = random.randint(8, 15)
                print(f"{Fore.YELLOW}Waiting {delay} seconds (Random Delay Active) before next download...{Style.RESET_ALL}")
                await asyncio.sleep(delay)
            else:
                # Minimal safety delay even if random is off
                await asyncio.sleep(2)
    except Exception as e:
        print(f"{Fore.RED}[Queue] Unexpected loop error: {e}{Style.RESET_ALL}")
    finally:
        state.queue_processing = False
        print(f"{Fore.CYAN}[Queue] Queue processing ended (state.queue_processing = False).{Style.RESET_ALL}")

