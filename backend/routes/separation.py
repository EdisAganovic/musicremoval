"""
Separation API Routes - handles vocal separation using Demucs/Spleeter.
"""
import os
import uuid
import asyncio
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException
from typing import List

from config import tasks, add_notification, log_console, get_full_library, save_to_library
from models import SeparateRequest, FolderScanRequest, FolderQueueProcessRequest

router = APIRouter(prefix="/api", tags=["separation"])


def run_separation(task_id: str, file_path: str, duration=None):
    """Run vocal separation on a file."""
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
        success = process_file(file_path, keep_temp=False, duration=duration, progress_callback=on_progress)

        if success:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Separation complete"

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
            library_entry = {
                "task_id": task_id,
                "url": "",
                "title": filename,
                "result_files": result_files,
                "status": "completed",
                "format": "separation",
                "source_file": file_path
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


@router.post("/separate")
async def separate_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and separate vocals from an audio file."""
    from modules.module_ffmpeg import get_file_metadata
    from colorama import Fore, Style

    task_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    metadata = get_file_metadata(file_path)

    print(f"\n{Fore.CYAN}=== File Upload Separation ==={Style.RESET_ALL}")
    print(f"File: {file_path}")

    # Create batch parent task for consistent UI polling
    tasks[batch_id] = {
        "batch": True,
        "batch_id": batch_id,
        "total_files": 1,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }

    # Create child task
    tasks[task_id] = {
        "task_id": task_id,
        "batch_id": batch_id,
        "status": "pending",
        "progress": 0,
        "current_step": "File uploaded",
        "result_files": [],
        "metadata": metadata,
        "file_path": file_path
    }

    batch_tasks_data = {
        "task_id": task_id,
        "file": file_path,
        "filename": file.filename,
        "status": "pending"
    }
    tasks[batch_id]["files"] = [batch_tasks_data]

    print(f"Task ID: {task_id}")
    print(f"Batch ID: {batch_id}")
    print(f"{Fore.GREEN}✓ Separation started{Style.RESET_ALL}\n")

    background_tasks.add_task(run_separation, task_id, file_path)

    return {"task_id": task_id, "batch_id": batch_id, "metadata": metadata}


@router.post("/separate-file")
async def separate_file(background_tasks: BackgroundTasks, payload: dict):
    """Separate vocals from an existing file on the server."""
    from modules.module_ffmpeg import get_file_metadata
    from colorama import Fore, Style

    file_path = payload.get("file_path")
    model = payload.get("model", "both")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    print(f"\n{Fore.CYAN}=== Single File Separation ==={Style.RESET_ALL}")
    print(f"File: {file_path}")

    task_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())
    metadata = get_file_metadata(file_path)

    # Create batch parent task for consistent UI polling
    tasks[batch_id] = {
        "batch": True,
        "batch_id": batch_id,
        "total_files": 1,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }

    # Create child task
    tasks[task_id] = {
        "task_id": task_id,
        "batch_id": batch_id,
        "status": "pending",
        "progress": 0,
        "current_step": "File queued for separation",
        "result_files": [],
        "metadata": metadata,
        "file_path": file_path
    }

    batch_tasks_data = {
        "task_id": task_id,
        "file": file_path,
        "filename": os.path.basename(file_path),
        "status": "pending"
    }
    tasks[batch_id]["files"] = [batch_tasks_data]

    print(f"Task ID: {task_id}")
    print(f"Batch ID: {batch_id}")
    print(f"{Fore.GREEN}✓ Separation started{Style.RESET_ALL}\n")

    background_tasks.add_task(run_separation, task_id, file_path)

    return {"task_id": task_id, "batch_id": batch_id, "metadata": metadata}


@router.post("/folder/scan")
async def scan_folder(payload: FolderScanRequest):
    """Scan a folder and return list of media files."""
    from colorama import Fore, Style
    from modules.module_ffmpeg import get_file_metadata
    import asyncio
    
    def perform_scan():
        print(f"\n{Fore.CYAN}=== Folder Scan Request ==={Style.RESET_ALL}")
        print(f"Folder path: {payload.folder_path}")

        if not payload.folder_path or not os.path.isdir(payload.folder_path):
            print(f"{Fore.RED}Folder not found: {payload.folder_path}{Style.RESET_ALL}")
            return None

        video_extensions = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.wmv')
        audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma')
        supported_extensions = video_extensions + audio_extensions

        media_files = []
        for f in os.listdir(payload.folder_path):
            if f.lower().endswith(supported_extensions):
                file_path = os.path.join(payload.folder_path, f)
                try:
                    metadata = get_file_metadata(file_path)
                    media_files.append({
                        "id": str(uuid.uuid4()),
                        "file_path": file_path,
                        "filename": f,
                        "metadata": metadata,
                        "selected": True
                    })
                    print(f"  Found: {f} ({metadata.get('duration', 'N/A')})")
                except Exception as e:
                    print(f"{Fore.YELLOW}Error getting metadata for {f}: {e}{Style.RESET_ALL}")
                    media_files.append({
                        "id": str(uuid.uuid4()),
                        "file_path": file_path,
                        "filename": f,
                        "metadata": {"duration": "N/A", "resolution": "N/A"},
                        "selected": True
                    })

        print(f"Total files found: {len(media_files)}")
        return media_files

    media_files = await asyncio.to_thread(perform_scan)
    
    if media_files is None:
        raise HTTPException(status_code=404, detail="Folder not found")

    if not media_files:
        print(f"{Fore.RED}No media files found in folder{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="No media files found in folder")

    queue_id = str(uuid.uuid4())
    tasks[queue_id] = {
        "queue": True,
        "folder": payload.folder_path,
        "files": media_files,
        "created_at": asyncio.get_event_loop().time()
    }

    print(f"Queue ID: {queue_id}")
    print(f"{Fore.GREEN}✓ Folder scan complete{Style.RESET_ALL}\n")

    return {
        "queue_id": queue_id,
        "folder": payload.folder_path,
        "files": media_files,
        "total_files": len(media_files)
    }


@router.post("/folder-queue/remove")
async def remove_from_folder_queue(payload: dict):
    """Remove a specific file from the queue."""
    queue_id = payload.get("queue_id")
    file_id = payload.get("file_id")

    if not queue_id or queue_id not in tasks:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue_data = tasks[queue_id]
    if not queue_data.get("queue"):
        raise HTTPException(status_code=400, detail="Not a queue task")

    queue_data["files"] = [f for f in queue_data["files"] if f["id"] != file_id]

    return {"status": "ok", "files": queue_data["files"], "total_files": len(queue_data["files"])}


@router.post("/folder-queue/process")
async def process_folder_queue(background_tasks: BackgroundTasks, payload: FolderQueueProcessRequest):
    """Start processing the selected files in the queue."""
    from colorama import Fore, Style
    
    print(f"\n{Fore.CYAN}=== Batch Processing Request ==={Style.RESET_ALL}")
    print(f"Queue ID: {payload.queue_id}")
    print(f"Model: {payload.model}")

    if not payload.queue_id or payload.queue_id not in tasks:
        print(f"{Fore.RED}Queue not found: {payload.queue_id}{Style.RESET_ALL}")
        raise HTTPException(status_code=404, detail="Queue not found")

    queue_data = tasks[payload.queue_id]
    if not queue_data.get("queue"):
        print(f"{Fore.RED}Not a queue task{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="Not a queue task")

    # Use explicitly selected files from payload if available, else use queue's internal state
    if payload.selected_files is not None:
        selected_files = [f for f in queue_data["files"] if f["file_path"] in payload.selected_files]
    else:
        selected_files = [f for f in queue_data["files"] if f.get("selected", True)]

    print(f"Total files in queue: {len(queue_data['files'])}")
    print(f"Selected files: {len(selected_files)}")

    if not selected_files:
        print(f"{Fore.RED}No files selected{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="No files selected for processing")

    batch_id = str(uuid.uuid4())
    batch_tasks_data = {
        "batch_id": batch_id,
        "folder": queue_data["folder"],
        "queue_id": payload.queue_id,
        "total_files": len(selected_files),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }

    print(f"Batch ID: {batch_id}")

    tasks[batch_id] = {
        "batch": True,
        **batch_tasks_data
    }

    for file_item in selected_files:
        task_id = str(uuid.uuid4())
        file_path = file_item["file_path"]

        print(f"  - Queuing: {file_item['filename']}")

        tasks[task_id] = {
            "task_id": task_id,
            "batch_id": batch_id,
            "status": "pending",
            "progress": 0,
            "current_step": "Queued",
            "file_path": file_path,
            "result_files": [],
            "metadata": file_item.get("metadata", {})
        }

        batch_tasks_data["files"].append({
            "task_id": task_id,
            "file": file_path,
            "filename": file_item["filename"],
            "status": "pending"
        })

        background_tasks.add_task(run_separation, task_id, file_path, payload.duration if hasattr(payload, 'duration') else None)

    print(f"{Fore.GREEN}✓ Batch processing started with {len(selected_files)} files{Style.RESET_ALL}\n")

    del tasks[payload.queue_id]

    return {"batch_id": batch_id, "total_files": len(selected_files), "files": batch_tasks_data["files"]}


@router.get("/folder-queue/{queue_id}")
async def get_folder_queue(queue_id: str):
    """Get the current queue status."""
    if queue_id not in tasks:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue_data = tasks[queue_id]
    if not queue_data.get("queue"):
        raise HTTPException(status_code=400, detail="Not a queue task")

    return {
        "queue_id": queue_id,
        "folder": queue_data["folder"],
        "files": queue_data["files"],
        "total_files": len(queue_data["files"])
    }


@router.get("/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch processing status."""
    if batch_id not in tasks:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch_data = tasks[batch_id]
    if not batch_data.get("batch"):
        raise HTTPException(status_code=400, detail="Not a batch task")

    # Update status for currently active tasks
    for file_item in batch_data.get("files", []):
        task_id = file_item.get("task_id")
        if task_id in tasks:
            task = tasks[task_id]
            file_item["status"] = task.get("status", file_item["status"])
            file_item["progress"] = task.get("progress", 0)
            file_item["current_step"] = task.get("current_step", "")

    return batch_data


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]
