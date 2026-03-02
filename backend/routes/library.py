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
    METADATA_CACHE_FILE, LIBRARY_FILE, metadata_cache,
    safe_remove
)

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library")
async def get_library():
    """Returns a list of all completed tasks and scans for existing files."""
    from colorama import Fore, Style
    import time

    def scan_library():
        library = get_full_library()

        existing_ids = {item.get("task_id") for item in library}
        existing_files = {os.path.abspath(os.path.normpath(item.get("result_files", [""])[0])) 
                          for item in library if item.get("result_files")}
        
        # Only exclude files that are ACTIVELY being processed — never block completed/failed tasks
        ACTIVE_STATUSES = {"processing", "downloading", "separating", "queued", "pending"}
        active_task_files = set()
        for t in tasks.values():
            if t.get("status") not in ACTIVE_STATUSES:
                continue
            # Source file currently being worked on
            f_path = t.get("file_path")
            if f_path:
                active_task_files.add(os.path.abspath(os.path.normpath(f_path)))
            # Result files being written right now
            for rf in t.get("result_files", []):
                if rf:
                    active_task_files.add(os.path.abspath(os.path.normpath(rf)))

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

                    file_path = os.path.abspath(os.path.normpath(os.path.join(root, filename)))
                    if os.path.isfile(file_path):
                        if file_path in existing_files or file_path in active_task_files:
                            continue

                        # Check if MD5 based ID already exists
                        task_id = hashlib.md5(file_path.encode()).hexdigest()

                        if task_id in existing_ids:
                            continue

                        metadata = get_file_metadata_cached(file_path)
                        
                        # Use file modification time as created_at for existing files
                        try:
                            file_mtime = os.path.getmtime(file_path)
                        except OSError:
                            file_mtime = time.time()

                        library.insert(0, {
                            "task_id": task_id,
                            "status": "completed",
                            "progress": 100,
                            "current_step": "Finished",
                            "result_files": [file_path],
                            "metadata": metadata,
                            "url": "",
                            "filename": filename,
                            "created_at": file_mtime
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
                    file_path = os.path.abspath(os.path.normpath(os.path.join(root, filename)))

                    if file_path in existing_files or file_path in active_task_files:
                        nomusic_skipped_existing += 1
                        continue

                    task_id = hashlib.md5(file_path.encode()).hexdigest()

                    if task_id in existing_ids:
                        nomusic_skipped_existing += 1
                        continue

                    nomusic_found += 1
                    nomusic_added += 1

                    metadata = get_file_metadata_cached(file_path)
                    
                    # Use file modification time as created_at for existing files
                    try:
                        file_mtime = os.path.getmtime(file_path)
                    except OSError:
                        file_mtime = time.time()

                    library.insert(0, {
                        "task_id": task_id,
                        "status": "completed",
                        "progress": 100,
                        "current_step": "Finished",
                        "result_files": [file_path],
                        "metadata": metadata,
                        "url": "",
                        "filename": filename,
                        "created_at": file_mtime
                    })
            print(f"{Fore.CYAN}[Library Scan] Nomusic: {nomusic_total} total, {nomusic_found} new, {nomusic_skipped_existing} skipped{Style.RESET_ALL}")

        # Repair existing entries with 'N/A' metadata
        library_changed = False
        for item in library:
            meta = item.get("metadata", {})
            if meta.get("duration") == "N/A":
                res_files = item.get("result_files", [])
                if res_files and os.path.exists(res_files[0]):
                    new_metadata = get_file_metadata_cached(res_files[0])
                    if new_metadata.get("duration") != "N/A":
                        item["metadata"] = new_metadata
                        library_changed = True

        # Sort by created_at timestamp (newest first)
        library.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        # Save library if we added new files or repaired metadata
        if nomusic_added > 0 or library_changed:
            from config import LIBRARY_FILE
            try:
                with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                    json.dump(library, f, indent=4)
            except (OSError, IOError, TypeError):
                pass

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
        if f and safe_remove(f):
            deleted.append(f)

    # Remove from library.json
    if os.path.exists(LIBRARY_FILE):
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                library = json.load(f)

            library = [item for item in library if item.get("task_id") != task_id]

            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=4)
        except (json.JSONDecodeError, OSError, IOError) as e:
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
    except (OSError, IOError, TypeError):
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


@router.post("/rename-file")
async def rename_file(payload: dict):
    """Rename a file in the library."""
    from config import sanitize_filename
    import hashlib
    
    task_id = payload.get("task_id")
    new_name = payload.get("new_name")
    
    if not task_id or not new_name:
        raise HTTPException(status_code=400, detail="task_id and new_name required")

    # Sanitize new name (remove invalid characters)
    new_name = sanitize_filename(new_name)
    
    # Find the item in library
    library = get_full_library()
    target_item = None
    for item in library:
        if item.get("task_id") == task_id:
            target_item = item
            break
            
    if not target_item:
        raise HTTPException(status_code=404, detail="File not found in library")
        
    old_path = target_item.get("result_files", [""])[0]
    if not old_path or not os.path.exists(old_path):
        raise HTTPException(status_code=404, detail="Physical file not found")
        
    # Construct new path
    directory = os.path.dirname(old_path)
    filename, extension = os.path.splitext(old_path)
    
    # Ensure new_name has extension if it doesn't already
    if not new_name.lower().endswith(extension.lower()):
        new_path = os.path.join(directory, new_name + extension)
    else:
        new_path = os.path.join(directory, new_name)
        
    if os.path.exists(new_path) and new_path.lower() != old_path.lower():
        raise HTTPException(status_code=400, detail="File with new name already exists")
        
    try:
        # Perform rename on disk
        # On Windows, os.rename handles case-only renames if not existing, but let's be safe.
        if new_path.lower() == old_path.lower() and new_path != old_path:
            # Case-only rename on Windows: needs a temporary step
            temp_path = old_path + ".tmp_rename"
            os.rename(old_path, temp_path)
            os.rename(temp_path, new_path)
        else:
            os.rename(old_path, new_path)
        
        # Update library entry
        new_task_id = hashlib.md5(new_path.encode()).hexdigest()
        
        # We need to update library.json to reflect the change
        # Update target_item (which is already a reference to an item in 'library' list)
        target_item["task_id"] = new_task_id
        target_item["result_files"] = [new_path]
        target_item["filename"] = os.path.basename(new_path)
        
        # Update library.json
        if os.path.exists(LIBRARY_FILE):
             with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=4)
            
        # Update metadata cache
        old_cache_key = None
        for key in list(metadata_cache.keys()):
            if old_path in key:
                old_cache_key = key
                break
        
        if old_cache_key:
            metadata = metadata_cache.pop(old_cache_key)
            # Generate new cache key
            new_mtime = os.path.getmtime(new_path)
            new_cache_key = f"{new_path}:{new_mtime}"
            metadata_cache[new_cache_key] = metadata
            save_metadata_cache()
            
        return {"status": "renamed", "new_path": new_path, "new_task_id": new_task_id}
        
    except Exception as e:
        print(f"Rename error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rename file: {str(e)}")
