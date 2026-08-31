"""
Separation API Routes - handles vocal separation using Demucs/Spleeter.
"""
import os
import time
import uuid
import asyncio
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, Form
from typing import List

from config import tasks, add_notification, log_console, get_full_library, save_to_library
from models import SeparateRequest, FolderScanRequest, FileListScanRequest, FolderQueueProcessRequest
from services.separation_service import enqueue_separation, run_separation

router = APIRouter(prefix="/api", tags=["separation"])


def _create_separation_task(background_tasks: BackgroundTasks, file_path: str, filename: str,
                             metadata: dict, model: str, skip_video_encoding: bool, current_step: str,
                             roformer_model: str = "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                             tiger_target: str = "dialogue_sfx", tiger_overlap: int = 50,
                             duration: int = None, export_instrumental: bool = False, remove_silence: bool = False,
                             super_keyframe: bool = False, resolution: str = "1080p"):
    """
    Shared bookkeeping for starting a single-file separation: creates the
    batch-parent task (for consistent UI polling across single/batch runs),
    the individual task entry, persists them, and schedules enqueue_separation.
    Used by both /separate (upload) and /separate-file (existing file).
    """
    from colorama import Fore, Style
    from services.persistence import save_tasks_sync

    task_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    tasks[batch_id] = {
        "batch": True,
        "batch_id": batch_id,
        "total_files": 1,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }

    tasks[task_id] = {
        "task_id": task_id,
        "batch_id": batch_id,
        "status": "pending",
        "progress": 0,
        "current_step": current_step,
        "result_files": [],
        "metadata": metadata,
        "file_path": file_path,
        "type": "separation",
        "created_at": time.time()
    }
    save_tasks_sync()

    tasks[batch_id]["files"] = [{
        "task_id": task_id,
        "file": file_path,
        "filename": filename,
        "status": "pending"
    }]

    print(f"Task ID: {task_id}")
    print(f"Batch ID: {batch_id}")
    print(f"{Fore.GREEN}✓ Separation queued (Resolution: {resolution}){Style.RESET_ALL}\n")

    enqueue_separation(
        task_id=task_id, file_path=file_path, duration=duration, model=model,
        roformer_model=roformer_model,
        tiger_target=tiger_target, tiger_overlap=tiger_overlap,
        skip_video_encoding=skip_video_encoding, super_keyframe=super_keyframe,
        resolution=resolution,
        export_instrumental=export_instrumental, remove_silence=remove_silence
    )

    return task_id, batch_id


@router.post("/separate")
async def separate_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...), model: str = Form("both"), roformer_model: str = Form("mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"), tiger_target: str = Form("dialogue_sfx"), tiger_overlap: int = Form(50), skip_video_encoding: bool = Form(False), super_keyframe: bool = Form(False), resolution: str = Form("1080p"), duration: int = Form(None), export_instrumental: bool = Form(False), remove_silence: bool = Form(False)):
    """Upload and separate vocals from an audio file."""
    from colorama import Fore, Style

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Fast initial metadata, background worker will refine it
    metadata = {"filename": file.filename, "is_video": True, "resolution": resolution}

    print(f"\n{Fore.CYAN}=== File Upload Separation ==={Style.RESET_ALL}")
    print(f"File: {file_path}")
    if duration:
        print(f"{Fore.YELLOW}Preview mode: limiting to first {duration}s{Style.RESET_ALL}")

    task_id, batch_id = _create_separation_task(
        background_tasks, file_path, file.filename, metadata,
        model, skip_video_encoding, "File queued for separation",
        roformer_model=roformer_model,
        tiger_target=tiger_target, tiger_overlap=tiger_overlap,
        duration=duration,
        export_instrumental=export_instrumental, remove_silence=remove_silence,
        super_keyframe=super_keyframe, resolution=resolution
    )

    return {"task_id": task_id, "batch_id": batch_id, "metadata": metadata}


@router.post("/separate-file")
async def separate_file(background_tasks: BackgroundTasks, payload: SeparateRequest):
    """Separate vocals from an existing file on the server."""
    from colorama import Fore, Style

    file_path = payload.file_path
    model = payload.model
    roformer_model = payload.roformer_model or "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"
    tiger_target = payload.tiger_target or "dialogue_sfx"
    tiger_overlap = payload.tiger_overlap or 50
    skip_video_encoding = payload.skip_video_encoding
    super_keyframe = payload.super_keyframe
    resolution = payload.resolution or "1080p"
    duration = payload.duration
    export_instrumental = payload.export_instrumental

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(file_path)
    metadata = {"filename": filename, "is_video": True, "resolution": resolution}

    print(f"\n{Fore.CYAN}=== Single File Separation ==={Style.RESET_ALL}")
    print(f"File: {file_path}")
    if duration:
        print(f"{Fore.YELLOW}Preview mode: limiting to first {duration}s{Style.RESET_ALL}")

    task_id, batch_id = _create_separation_task(
        background_tasks, file_path, filename, metadata,
        model, skip_video_encoding, "File queued for separation",
        roformer_model=roformer_model,
        tiger_target=tiger_target, tiger_overlap=tiger_overlap,
        duration=duration,
        export_instrumental=export_instrumental, remove_silence=payload.remove_silence,
        super_keyframe=super_keyframe, resolution=resolution
    )

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
                    from modules.module_processor import is_file_processed
                    metadata = get_file_metadata(file_path)
                    existing_output = is_file_processed(file_path)
                    media_files.append({
                        "id": str(uuid.uuid4()),
                        "file_path": file_path,
                        "filename": f,
                        "metadata": metadata,
                        "selected": not bool(existing_output), # Auto-deselect if already processed
                        "already_processed": bool(existing_output),
                        "output_path": existing_output
                    })
                    if existing_output:
                        print(f"  Found (ALREADY PROCESSED): {f}")
                    else:
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
        "created_at": time.time()
    }

    print(f"Queue ID: {queue_id}")
    print(f"{Fore.GREEN}✓ Folder scan complete{Style.RESET_ALL}\n")

    return {
        "queue_id": queue_id,
        "folder": payload.folder_path,
        "files": media_files,
        "total_files": len(media_files)
    }


@router.post("/folder/scan-files")
async def scan_file_list(payload: FileListScanRequest):
    """
    Build a folder-queue entry directly from an explicit list of file paths
    (e.g. a multi-select in the Library tab), skipping the directory-scan step.
    Reuses the same queue/batch machinery as /folder/scan + /folder-queue/process
    so bulk separation gets the same progress tracking as folder batch processing.
    """
    from colorama import Fore, Style
    from modules.module_ffmpeg import get_file_metadata
    from modules.module_processor import is_file_processed

    def build_media_files():
        media_files = []
        for file_path in payload.file_paths:
            if not file_path or not os.path.isfile(file_path):
                print(f"{Fore.YELLOW}Skipping missing file: {file_path}{Style.RESET_ALL}")
                continue
            try:
                metadata = get_file_metadata(file_path)
                existing_output = is_file_processed(file_path)
                media_files.append({
                    "id": str(uuid.uuid4()),
                    "file_path": file_path,
                    "filename": os.path.basename(file_path),
                    "metadata": metadata,
                    "selected": True,
                    "already_processed": bool(existing_output),
                    "output_path": existing_output
                })
            except Exception as e:
                print(f"{Fore.YELLOW}Error getting metadata for {file_path}: {e}{Style.RESET_ALL}")
                media_files.append({
                    "id": str(uuid.uuid4()),
                    "file_path": file_path,
                    "filename": os.path.basename(file_path),
                    "metadata": {"duration": "N/A", "resolution": "N/A"},
                    "selected": True
                })
        return media_files

    media_files = await asyncio.to_thread(build_media_files)

    if not media_files:
        raise HTTPException(status_code=400, detail="None of the selected files could be found")

    queue_id = str(uuid.uuid4())
    tasks[queue_id] = {
        "queue": True,
        "folder": None,
        "files": media_files,
        "created_at": time.time()
    }

    print(f"{Fore.GREEN}✓ Built queue {queue_id} from {len(media_files)} selected library file(s){Style.RESET_ALL}")

    return {
        "queue_id": queue_id,
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
            "type": "separation",
            "result_files": [],
            "metadata": file_item.get("metadata", {})
        }

        batch_tasks_data["files"].append({
            "task_id": task_id,
            "file": file_path,
            "filename": file_item["filename"],
            "status": "pending"
        })

        enqueue_separation(
            task_id=task_id,
            file_path=file_path,
            duration=payload.duration if hasattr(payload, 'duration') else None,
            model=payload.model,
            roformer_model=payload.roformer_model or "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
            tiger_target=payload.tiger_target or "dialogue_sfx",
            tiger_overlap=payload.tiger_overlap or 50,
            skip_video_encoding=payload.skip_video_encoding,
            super_keyframe=payload.super_keyframe,
            resolution=payload.resolution or "1080p",
            export_instrumental=payload.export_instrumental,
            remove_silence=payload.remove_silence
        )

    print(f"{Fore.GREEN}✓ Batch processing queued with {len(selected_files)} files{Style.RESET_ALL}\n")

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


@router.post("/separation-queue/clear")
async def clear_queue_route():
    """Clear all pending tasks in the separation queue."""
    from services.separation_service import clear_separation_queue
    cleared = clear_separation_queue()
    return {"status": "success", "cleared_tasks": cleared}
