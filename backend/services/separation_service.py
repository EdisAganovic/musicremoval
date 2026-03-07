"""
Separation service - handles vocal separation using Demucs/Spleeter.
"""
import os
from config import tasks, add_notification, log_console, get_full_library, save_to_library


def run_separation(task_id: str, file_path: str, duration=None, model="both"):
    """
    Run vocal separation on a file.
    
    Args:
        task_id: Unique task identifier
        file_path: Path to the file to process
        duration: Optional duration limit in seconds
        model: Separation model to use (spleeter, demucs, both)
    
    Returns:
        None (updates tasks dict with results)
    """
    from modules.module_processor import process_file
    from modules.module_ffmpeg import download_ffmpeg

    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["current_step"] = "Starting separation..."

        # Update batch parent if exists
        batch_id = tasks[task_id].get("batch_id")
        if batch_id and batch_id in tasks:
            tasks[batch_id]["status"] = "processing"
            tasks[batch_id]["current_step"] = "Processing file 1/1..."

        if not download_ffmpeg():
            raise Exception("FFmpeg download failed")

        def on_progress(step, progress):
            if task_id in tasks:
                tasks[task_id]["current_step"] = step
                tasks[task_id]["progress"] = progress
                
                # Periodically save to disk (every 10%)
                if int(progress) % 10 == 0:
                    from services.persistence import save_tasks_sync
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
        success = process_file(file_path, keep_temp=False, duration=duration, progress_callback=on_progress, model=model)

        if success:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Separation complete"
            from services.persistence import save_tasks_sync
            save_tasks_sync()

            # Update parent batch counters
            batch_id = tasks[task_id].get("batch_id")
            if batch_id and batch_id in tasks:
                tasks[batch_id]["processed"] = tasks[batch_id].get("processed", 0) + 1
                tasks[batch_id]["success"] = tasks[batch_id].get("success", 0) + 1
                tasks[batch_id]["status"] = "completed"
                tasks[batch_id]["current_step"] = "All files processed"
                tasks[batch_id]["progress"] = 100
                # Update file status in batch
                for file_item in tasks[batch_id].get("files", []):
                    if file_item.get("task_id") == task_id:
                        file_item["status"] = "completed"
                        file_item["progress"] = 100

            # Find output files - fix path to be relative to project root
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
            if not result_files and isinstance(success, str):
                result_files = [success]

            tasks[task_id]["result_files"] = result_files

            # Save to library
            from services.persistence import get_file_metadata_cached
            library_entry = {
                "task_id": task_id,
                "url": "",
                "title": filename,
                "result_files": result_files,
                "status": "completed",
                "format": "separation",
                "source_file": file_path,
                "metadata": get_file_metadata_cached(result_files[0]) if result_files else {}
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
                tasks[batch_id]["status"] = "failed"
                tasks[batch_id]["current_step"] = "File processing failed"
                # Update file status in batch
                for file_item in tasks[batch_id].get("files", []):
                    if file_item.get("task_id") == task_id:
                        file_item["status"] = "failed"

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
            tasks[batch_id]["status"] = "failed"
            tasks[batch_id]["current_step"] = f"Error: {error_msg[:50]}"
            # Update file status in batch
            for file_item in tasks[batch_id].get("files", []):
                if file_item.get("task_id") == task_id:
                    file_item["status"] = "failed"

        add_notification("error", "Separation Error", f"Error processing '{file_path}': {error_msg[:100]}")