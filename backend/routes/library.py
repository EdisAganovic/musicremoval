"""
Library API Routes - handles media library management.
"""
import os
import hashlib
import json
import subprocess
from fastapi import APIRouter, HTTPException
from typing import List

from config import (
    tasks, get_full_library, save_to_library, 
    get_file_metadata_cached, save_metadata_cache,
    METADATA_CACHE_FILE, LIBRARY_FILE, metadata_cache
)

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library")
async def get_library():
    """Returns a list of all completed tasks and scans for existing files."""
    from colorama import Fore, Style
    
    def scan_library():
        library = get_full_library()

        existing_ids = {item.get("task_id") for item in library}
        existing_files = {item.get("result_files", [""])[0] for item in library if item.get("result_files")}

        VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.mpeg', '.mpg', '.3gp'}
        AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.opus'}
        NOMUSIC_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

        # Scan download folder
        download_folder = "download"
        if os.path.exists(download_folder):
            for root, dirs, files in os.walk(download_folder):
                for filename in files:
                    _, ext = os.path.splitext(filename)
                    if ext.lower() not in VIDEO_EXTENSIONS:
                        continue

                    file_path = os.path.join(root, filename)
                    if os.path.isfile(file_path) and file_path not in existing_files:
                        task_id = hashlib.md5(file_path.encode()).hexdigest()

                        if task_id in existing_ids:
                            continue

                        metadata = get_file_metadata_cached(file_path)

                        library.insert(0, {
                            "task_id": task_id,
                            "status": "completed",
                            "progress": 100,
                            "current_step": "Finished",
                            "result_files": [file_path],
                            "metadata": metadata,
                            "url": "",
                            "filename": filename
                        })

        # Scan nomusic folder
        nomusic_folder = "nomusic"
        nomusic_added = 0
        if os.path.exists(nomusic_folder):
            nomusic_total = 0
            nomusic_found = 0
            nomusic_skipped_existing = 0

            for root, dirs, files in os.walk(nomusic_folder):
                for filename in files:
                    _, ext = os.path.splitext(filename)

                    if ext.lower() not in NOMUSIC_EXTENSIONS:
                        continue
                    nomusic_total += 1
                    file_path = os.path.join(root, filename)

                    if file_path in existing_files:
                        nomusic_skipped_existing += 1
                        continue

                    task_id = hashlib.md5(file_path.encode()).hexdigest()

                    if task_id in existing_ids:
                        nomusic_skipped_existing += 1
                        continue

                    nomusic_found += 1
                    nomusic_added += 1

                    metadata = get_file_metadata_cached(file_path)

                    library.insert(0, {
                        "task_id": task_id,
                        "status": "completed",
                        "progress": 100,
                        "current_step": "Finished",
                        "result_files": [file_path],
                        "metadata": metadata,
                        "url": "",
                        "filename": filename
                    })
            print(f"{Fore.CYAN}[Library Scan] Nomusic: {nomusic_total} total, {nomusic_found} new, {nomusic_skipped_existing} skipped{Style.RESET_ALL}")

        library.sort(key=lambda x: x.get("task_id", ""), reverse=True)
        save_metadata_cache()
        return library

    import asyncio
    return await asyncio.to_thread(scan_library)


@router.post("/delete-file")
async def delete_file(payload: dict):
    """Delete a file from the library."""
    task_id = payload.get("task_id")
    file_path = payload.get("file_path")

    # Find file to delete
    files_to_delete = []
    
    if file_path:
        files_to_delete = [file_path]
    elif task_id:
        # Find in library
        library = get_full_library()
        for item in library:
            if item.get("task_id") == task_id:
                files_to_delete = item.get("result_files", [])
                break
        
        # Also check tasks
        if not files_to_delete and task_id in tasks:
            files_to_delete = tasks[task_id].get("result_files", [])

    # Delete files
    deleted = []
    for f in files_to_delete:
        if f and os.path.exists(f):
            try:
                os.remove(f)
                deleted.append(f)
            except Exception as e:
                print(f"Error deleting {f}: {e}")

    # Remove from library.json
    if os.path.exists(LIBRARY_FILE):
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                library = json.load(f)
            
            library = [item for item in library if item.get("task_id") != task_id]
            
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=4)
        except Exception as e:
            print(f"Error updating library: {e}")

    # Remove from tasks
    tasks.pop(task_id, None)

    # Remove from metadata cache
    stale_keys = [k for k in metadata_cache if any(f in k for f in files_to_delete)]
    for key in stale_keys:
        metadata_cache.pop(key, None)

    try:
        with open(METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata_cache, f, indent=4)
    except:
        pass

    return {"status": "deleted", "files": deleted}


@router.post("/open-file")
async def open_file(payload: dict):
    """Open a file with default application."""
    path = payload.get("path")

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # macOS/Linux
            subprocess.run(['open', path] if os.uname().sysname == 'Darwin' else ['xdg-open', path])
        return {"status": "opened", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {str(e)}")


@router.post("/open-folder")
async def open_folder(payload: dict):
    """Open a folder in file explorer."""
    path = payload.get("path")

    if not path:
        raise HTTPException(status_code=400, detail="Path required")

    # Resolve relative paths
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), '..', path)

    if not os.path.isdir(path):
        # Try to create it
        os.makedirs(path, exist_ok=True)

    try:
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.run(['open', path] if os.uname().sysname == 'Darwin' else ['xdg-open', path])
        return {"status": "opened", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}")


@router.get("/presets")
async def get_presets():
    """Get available quality presets."""
    presets_file = "data/video.json"

    if os.path.exists(presets_file):
        try:
            with open(presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "presets": data.get("presets", {}),
                    "current_preset": data.get("current_preset", "balanced")
                }
        except:
            pass

    return {
        "presets": {
            "fast": {"label": "Fast (Small Size)"},
            "balanced": {"label": "Balanced (Recommended)"},
            "quality": {"label": "High Quality (Large Size)"}
        },
        "current_preset": "balanced"
    }


@router.post("/presets")
async def set_preset(payload: dict):
    """Set the current quality preset."""
    preset_name = payload.get("preset")
    presets_file = "data/video.json"

    data = {"presets": {}, "current_preset": preset_name}

    if os.path.exists(presets_file):
        try:
            with open(presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass

    data["current_preset"] = preset_name

    with open(presets_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return {"status": "ok", "current_preset": preset_name}
