"""
Separation service - handles vocal separation using Demucs/Spleeter with FIFO Queue processing.
"""
import os
import time
import queue
import threading
from colorama import Fore, Style
from config import tasks, add_notification, log_console, get_full_library, save_to_library
from services.persistence import save_tasks_sync

# Thread-safe FIFO separation queue
_separation_queue = queue.Queue()
_worker_lock = threading.Lock()
_worker_thread = None
_current_running_task_id = None


def get_current_separation_task_id():
    """Returns the task_id of the currently executing separation, or None."""
    global _current_running_task_id
    return _current_running_task_id


def get_separation_queue_length():
    """Returns the number of tasks currently waiting in the separation queue."""
    return _separation_queue.qsize()


def clear_separation_queue():
    """Drains all pending items from the separation queue."""
    cleared = 0
    while not _separation_queue.empty():
        try:
            item = _separation_queue.get_nowait()
            t_id = item.get("task_id")
            if t_id and t_id in tasks:
                tasks[t_id]["status"] = "cancelled"
            _separation_queue.task_done()
            cleared += 1
        except queue.Empty:
            break
    save_tasks_sync()
    return cleared


def enqueue_separation(task_id: str, file_path: str, duration=None, model="both",
                       roformer_model="mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                       tiger_target="dialogue_sfx", tiger_overlap=50,
                       skip_video_encoding=False, super_keyframe=False, resolution="1080p", export_instrumental=False, remove_silence=False):
    """
    Adds a separation task to the FIFO queue and ensures the background worker is running.
    Tasks are processed strictly one at a time to prevent GPU VRAM contention and process collisions.
    """
    global _worker_thread

    # Queue item dictionary
    item = {
        "task_id": task_id,
        "file_path": file_path,
        "duration": duration,
        "model": model,
        "roformer_model": roformer_model,
        "tiger_target": tiger_target,
        "tiger_overlap": tiger_overlap,
        "skip_video_encoding": skip_video_encoding,
        "super_keyframe": super_keyframe,
        "resolution": resolution,
        "export_instrumental": export_instrumental,
        "remove_silence": remove_silence
    }

    _separation_queue.put(item)
    q_len = _separation_queue.qsize()

    # If another task is already running, clearly indicate queue position
    if _current_running_task_id is not None or q_len > 1:
        if task_id in tasks:
            tasks[task_id]["status"] = "pending"
            tasks[task_id]["current_step"] = f"Queued (waiting in line, position #{q_len})"
            save_tasks_sync()
        print(f"{Fore.CYAN}[Separation Queue] Task {task_id} queued at position #{q_len} ({os.path.basename(file_path)}){Style.RESET_ALL}")
    else:
        if task_id in tasks:
            tasks[task_id]["status"] = "pending"
            tasks[task_id]["current_step"] = "Queued"
            save_tasks_sync()

    # Ensure worker thread is active
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(target=_separation_worker_loop, daemon=True, name="SeparationWorker")
            _worker_thread.start()


def _separation_worker_loop():
    """
    Continuous worker loop that pulls separation tasks from the FIFO queue and processes them sequentially.
    """
    global _current_running_task_id

    while True:
        try:
            # Block briefly to wait for next item or timeout to allow thread lifecycle management
            item = _separation_queue.get(timeout=3.0)
        except queue.Empty:
            # Queue is empty, exit worker thread gracefully
            with _worker_lock:
                _current_running_task_id = None
                break

        task_id = item["task_id"]
        _current_running_task_id = task_id

        # Check if task was cancelled while sitting in queue
        if task_id in tasks and tasks[task_id].get("status") == "cancelled":
            print(f"{Fore.YELLOW}[Separation Queue] Skipping cancelled task {task_id}{Style.RESET_ALL}")
            _separation_queue.task_done()
            continue

        try:
            print(f"\n{Fore.GREEN}[Separation Queue] Starting execution of task {task_id} ({os.path.basename(item['file_path'])}){Style.RESET_ALL}")
            _execute_separation(
                task_id=task_id,
                file_path=item["file_path"],
                duration=item["duration"],
                model=item["model"],
                roformer_model=item.get("roformer_model", "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"),
                tiger_target=item.get("tiger_target", "dialogue_sfx"),
                tiger_overlap=item.get("tiger_overlap", 50),
                skip_video_encoding=item.get("skip_video_encoding", False),
                super_keyframe=item.get("super_keyframe", False),
                resolution=item.get("resolution", "1080p"),
                export_instrumental=item.get("export_instrumental", False),
                remove_silence=item.get("remove_silence", False)
            )
        except Exception as e:
            print(f"{Fore.RED}[Separation Queue] Unhandled exception in task {task_id}: {e}{Style.RESET_ALL}")
        finally:
            _current_running_task_id = None
            _separation_queue.task_done()
            save_tasks_sync()


def _execute_separation(task_id: str, file_path: str, duration=None, model="both",
                        roformer_model="mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                        tiger_target="dialogue_sfx", tiger_overlap=50,
                        skip_video_encoding=False, super_keyframe=False, resolution="1080p", export_instrumental=False, remove_silence=False):
    """
    Internal execution of vocal separation on a single file.
    """
    from modules.module_processor import process_file
    from modules.module_ffmpeg import download_ffmpeg

    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["current_step"] = "Starting separation..."
        tasks[task_id]["start_time"] = time.time()

        # Update batch parent if exists
        batch_id = tasks[task_id].get("batch_id")
        if batch_id and batch_id in tasks:
            tasks[batch_id]["status"] = "processing"
            processed_count = tasks[batch_id].get("processed", 0)
            total_count = tasks[batch_id].get("total_files", 1)
            tasks[batch_id]["current_step"] = f"Processing file {processed_count + 1}/{total_count}..."

        if not download_ffmpeg():
            raise Exception("FFmpeg download failed")

        def on_progress(step, progress):
            if task_id in tasks:
                tasks[task_id]["current_step"] = step
                tasks[task_id]["progress"] = progress
                
                # Periodically save to disk (every 10%)
                if int(progress) % 10 == 0:
                    save_tasks_sync()

            # Update batch parent progress
            batch_id = tasks.get(task_id, {}).get("batch_id")
            if batch_id and batch_id in tasks:
                tasks[batch_id]["current_step"] = f"{step} ({progress}%)"
                tasks[batch_id]["progress"] = progress
                # Update file status in batch
                for file_item in tasks[batch_id].get("files", []):
                    if file_item.get("task_id") == task_id:
                        file_item["status"] = "processing"
                        file_item["progress"] = progress
                        file_item["current_step"] = step

        filename = os.path.basename(file_path)
        success_result, phase_timings, instrumental_path = process_file(
            file_path, keep_temp=False, duration=duration, progress_callback=on_progress,
            model=model, roformer_model=roformer_model,
            tiger_target=tiger_target, tiger_overlap=tiger_overlap,
            skip_video_encoding=skip_video_encoding, super_keyframe=super_keyframe,
            resolution=resolution,
            export_instrumental=export_instrumental, remove_silence=remove_silence
        )

        if success_result:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Separation complete"
            tasks[task_id]["end_time"] = time.time()
            tasks[task_id]["processing_time"] = tasks[task_id]["end_time"] - tasks[task_id]["start_time"]
            tasks[task_id]["timings"] = phase_timings
            
            save_tasks_sync()

            # Update parent batch counters
            batch_id = tasks[task_id].get("batch_id")
            if batch_id and batch_id in tasks:
                tasks[batch_id]["processed"] = tasks[batch_id].get("processed", 0) + 1
                tasks[batch_id]["success"] = tasks[batch_id].get("success", 0) + 1
                total_files = tasks[batch_id].get("total_files", 1)
                if tasks[batch_id]["processed"] >= total_files:
                    tasks[batch_id]["status"] = "completed"
                    tasks[batch_id]["current_step"] = "All files processed"
                    tasks[batch_id]["progress"] = 100
                
                # Update file status in batch
                for file_item in tasks[batch_id].get("files", []):
                    if file_item.get("task_id") == task_id:
                        file_item["status"] = "completed"
                        file_item["progress"] = 100
                        file_item["current_step"] = "Complete"

            # Find output files - relative to project root
            output_dir = os.path.abspath('nomusic')

            # Support both audio and video filenames by stripping UUID if present
            raw_name = filename
            if "_" in raw_name and len(raw_name.split("_")[0]) == 36:
                clean_name_base = os.path.splitext("_".join(raw_name.split("_")[1:]))[0]
            else:
                clean_name_base = os.path.splitext(raw_name)[0]

            result_files = []
            if os.path.exists(output_dir):
                for f in os.listdir(output_dir):
                    if clean_name_base in f and f != filename:
                        result_files.append(os.path.join(output_dir, f))

            # Fallback to the direct return value if we couldn't find matching files via scan
            if not result_files and isinstance(success_result, str):
                result_files = [success_result]

            tasks[task_id]["result_files"] = result_files
            if instrumental_path:
                tasks[task_id]["instrumental_file"] = instrumental_path

            # Save to library
            from services.persistence import get_file_metadata_cached
            library_entry = {
                "task_id": task_id,
                "url": "",
                "title": filename,
                "result_files": result_files,
                "instrumental_file": instrumental_path,
                "status": "completed",
                "format": "separation",
                "source_file": file_path,
                "metadata": get_file_metadata_cached(result_files[0]) if result_files else {},
                "model": model,
                "skip_video_encoding": skip_video_encoding,
                "start_time": tasks[task_id].get("start_time"),
                "end_time": tasks[task_id].get("end_time"),
                "processing_time": tasks[task_id].get("processing_time"),
                "timings": tasks[task_id].get("timings")
            }
            save_to_library(library_entry)

            # Refresh library to ensure UI gets updated data
            get_full_library()

            add_notification(
                "success",
                "Separation Complete",
                f"Vocals separated from {filename}",
                {"task_id": task_id, "files": result_files}
            )
        else:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Separation failed"

            # Update parent batch counters
            batch_id = tasks[task_id].get("batch_id")
            if batch_id and batch_id in tasks:
                tasks[batch_id]["processed"] = tasks[batch_id].get("processed", 0) + 1
                tasks[batch_id]["failed"] = tasks[batch_id].get("failed", 0) + 1
                total_files = tasks[batch_id].get("total_files", 1)
                if tasks[batch_id]["processed"] >= total_files:
                    tasks[batch_id]["status"] = "completed" if tasks[batch_id]["success"] > 0 else "failed"
                    tasks[batch_id]["current_step"] = "Batch finished"
                
                # Update file status in batch
                for file_item in tasks[batch_id].get("files", []):
                    if file_item.get("task_id") == task_id:
                        file_item["status"] = "failed"
                        file_item["current_step"] = "Failed"

            add_notification("error", "Separation Failed", f"Failed to process {filename}")

    except Exception as e:
        error_msg = str(e)
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Error: {error_msg[:100]}"

        # Update parent batch counters
        batch_id = tasks[task_id].get("batch_id")
        if batch_id and batch_id in tasks:
            tasks[batch_id]["processed"] = tasks[batch_id].get("processed", 0) + 1
            tasks[batch_id]["failed"] = tasks[batch_id].get("failed", 0) + 1
            total_files = tasks[batch_id].get("total_files", 1)
            if tasks[batch_id]["processed"] >= total_files:
                tasks[batch_id]["status"] = "completed" if tasks[batch_id]["success"] > 0 else "failed"
                tasks[batch_id]["current_step"] = "Batch finished"
            
            # Update file status in batch
            for file_item in tasks[batch_id].get("files", []):
                if file_item.get("task_id") == task_id:
                    file_item["status"] = "failed"
                    file_item["current_step"] = f"Error: {error_msg[:50]}"

        add_notification("error", "Separation Error", f"Error processing '{file_path}': {error_msg[:100]}")


def run_separation(task_id: str, file_path: str, duration=None, model="both",
                   skip_video_encoding=False, super_keyframe=False, resolution="1080p", export_instrumental=False, remove_silence=False):
    """
    Backwards-compatible interface. Automatically routes through the FIFO separation queue.
    """
    enqueue_separation(
        task_id=task_id,
        file_path=file_path,
        duration=duration,
        model=model,
        skip_video_encoding=skip_video_encoding,
        super_keyframe=super_keyframe,
        resolution=resolution,
        export_instrumental=export_instrumental,
        remove_silence=remove_silence
    )