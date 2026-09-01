"""
Library API Routes - handles media library management.
"""
import os
import hashlib
import json
import subprocess
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from typing import List

from config import (
    tasks, get_full_library, save_to_library,
    get_file_metadata_cached, save_metadata_cache,
    METADATA_CACHE_FILE, LIBRARY_FILE, metadata_cache,
    safe_remove, is_path_within_allowed_roots, log_console
)
from core.constants import DOWNLOAD_DIR, NOMUSIC_DIR

router = APIRouter(prefix="/api", tags=["library"])

# Allowed root directories that media/stream/open endpoints may access.
# Everything outside these is rejected as a path-traversal attempt.
ALLOWED_ROOTS = [
    NOMUSIC_DIR,
    DOWNLOAD_DIR,
    os.path.abspath("uploads"),
    os.path.abspath("projects"),
    os.path.abspath("_temp"),
]


# In-memory library cache for instantaneous responses on repeated polling
_library_cache = {
    "data": None,
    "timestamp": 0.0,
    "ttl": 4.0  # seconds to serve directly from memory without re-scanning disk
}

def invalidate_library_cache():
    """Forces the next get_library call to perform a fresh disk scan."""
    _library_cache["timestamp"] = 0.0
    _library_cache["data"] = None


def _fast_scan_dir_files(folder_path: str, allowed_exts: set) -> list:
    """Fast recursive file discovery using os.scandir."""
    found_files = []
    if not os.path.exists(folder_path):
        return found_files
    
    stack = [os.path.abspath(folder_path)]
    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        _, ext = os.path.splitext(entry.name)
                        if ext.lower() in allowed_exts:
                            found_files.append((entry.path, entry.name))
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except (OSError, PermissionError):
            continue
    return found_files


@router.get("/library")
async def get_library(force: bool = False):
    """Returns a list of all completed tasks and scans for existing files."""
    import time
    now = time.time()

    # Instant response if cache is fresh and not forced
    if not force and _library_cache["data"] is not None and (now - _library_cache["timestamp"]) < _library_cache["ttl"]:
        return _library_cache["data"]

    def scan_library():
        library = get_full_library()

        existing_ids = {item.get("task_id") for item in library if isinstance(item, dict)}
        existing_files = {
            os.path.abspath(os.path.normpath(item.get("result_files", [""])[0])) 
            for item in library if isinstance(item, dict) and item.get("result_files")
        }
        
        # Only exclude files that are ACTIVELY being processed
        ACTIVE_STATUSES = {"processing", "downloading", "separating", "queued", "pending"}
        active_task_files = set()
        for t in tasks.values():
            if not isinstance(t, dict) or t.get("status") not in ACTIVE_STATUSES:
                continue
            f_path = t.get("file_path")
            if f_path:
                active_task_files.add(os.path.abspath(os.path.normpath(f_path)))
            for rf in t.get("result_files", []):
                if rf:
                    active_task_files.add(os.path.abspath(os.path.normpath(rf)))

        VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.mpeg', '.mpg', '.3gp'}
        AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg', '.wma', '.opus'}
        NOMUSIC_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

        new_items_added = 0
        metadata_changed = False

        # 1. Fast scan download folder (audio AND video)
        download_files = _fast_scan_dir_files(DOWNLOAD_DIR, VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)
        for file_path, filename in download_files:
            abs_norm = os.path.abspath(os.path.normpath(file_path))
            if abs_norm in existing_files or abs_norm in active_task_files:
                continue

            task_id = hashlib.md5(abs_norm.encode()).hexdigest()
            if task_id in existing_ids:
                continue

            existing_files.add(abs_norm)
            existing_ids.add(task_id)
            new_items_added += 1

            metadata = get_file_metadata_cached(abs_norm)
            try:
                file_mtime = os.path.getmtime(abs_norm)
            except OSError:
                file_mtime = time.time()

            library.insert(0, {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "current_step": "Finished",
                "result_files": [abs_norm],
                "metadata": metadata,
                "url": "",
                "filename": filename,
                "created_at": file_mtime
            })

        # 2. Fast scan nomusic folder
        nomusic_files = _fast_scan_dir_files(NOMUSIC_DIR, NOMUSIC_EXTENSIONS)
        for file_path, filename in nomusic_files:
            abs_norm = os.path.abspath(os.path.normpath(file_path))
            if abs_norm in existing_files or abs_norm in active_task_files:
                continue

            task_id = hashlib.md5(abs_norm.encode()).hexdigest()
            if task_id in existing_ids:
                continue

            existing_files.add(abs_norm)
            existing_ids.add(task_id)
            new_items_added += 1

            metadata = get_file_metadata_cached(abs_norm)
            try:
                file_mtime = os.path.getmtime(abs_norm)
            except OSError:
                file_mtime = time.time()

            library.insert(0, {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "current_step": "Finished",
                "result_files": [abs_norm],
                "metadata": metadata,
                "url": "",
                "filename": filename,
                "created_at": file_mtime
            })

        # 3. Sort by created_at timestamp (newest first)
        library.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        # Save library to disk only if changes were made
        if new_items_added > 0:
            from config import LIBRARY_FILE
            try:
                library_copy = list(library)
                with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                    json.dump(library_copy, f, indent=4)
            except (OSError, IOError, TypeError):
                pass

        # Update in-memory cache
        _library_cache["data"] = library
        _library_cache["timestamp"] = time.time()

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
        cache_copy = dict(metadata_cache)
        with open(METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_copy, f, indent=4)
    except (OSError, IOError, TypeError):
        pass

    invalidate_library_cache()

    return {"status": "deleted", "files": deleted}


@router.post("/library/move")
@router.post("/move-file")
async def move_files(payload: dict):
    """Move one or more files to a target folder/subfolder."""
    import shutil
    task_ids = payload.get("task_ids", [])
    file_paths = payload.get("file_paths", [])
    if payload.get("task_id"):
        task_ids.append(payload["task_id"])
    if payload.get("file_path"):
        file_paths.append(payload["file_path"])

    target_category = payload.get("target_category", "download")  # 'download' or 'nomusic'
    target_subfolder = payload.get("target_subfolder")  # None, "", "(Direct Files)", or subfolder name

    if target_subfolder in (None, "", "(Direct Files)", "root", "Root"):
        target_dir = os.path.abspath(target_category)
    else:
        clean_subfolder = os.path.basename(target_subfolder.strip())
        target_dir = os.path.abspath(os.path.join(target_category, clean_subfolder))

    os.makedirs(target_dir, exist_ok=True)

    library = get_full_library()
    moved = []
    task_map = {item.get("task_id"): item for item in library if isinstance(item, dict)}

    all_targets = []
    for tid in task_ids:
        if tid in task_map:
            for rf in task_map[tid].get("result_files", []):
                all_targets.append((tid, rf))

    for fp in file_paths:
        tid = None
        for item in library:
            if isinstance(item, dict) and fp in item.get("result_files", []):
                tid = item.get("task_id")
                break
        all_targets.append((tid, fp))

    library_changed = False
    for tid, src_file in all_targets:
        if not src_file or not os.path.exists(src_file):
            continue

        src_file_abs = os.path.abspath(os.path.normpath(src_file))
        filename = os.path.basename(src_file_abs)
        dst_file_abs = os.path.abspath(os.path.normpath(os.path.join(target_dir, filename)))

        if src_file_abs == dst_file_abs:
            continue

        try:
            # Handle destination collision safely
            if os.path.exists(dst_file_abs):
                base_name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dst_file_abs):
                    dst_file_abs = os.path.abspath(os.path.normpath(os.path.join(target_dir, f"{base_name}_{counter}{ext}")))
                    counter += 1

            shutil.move(src_file_abs, dst_file_abs)
            moved.append({"old": src_file_abs, "new": dst_file_abs})

            # Update library entry
            if tid and tid in task_map:
                task_map[tid]["result_files"] = [dst_file_abs]
                library_changed = True
            else:
                for item in library:
                    if isinstance(item, dict) and src_file_abs in [os.path.abspath(os.path.normpath(f)) for f in item.get("result_files", [])]:
                        item["result_files"] = [dst_file_abs]
                        library_changed = True
        except (OSError, IOError, shutil.Error) as e:
            print(f"Error moving file {src_file_abs}: {e}")

    if library_changed:
        from config import LIBRARY_FILE
        try:
            library_copy = list(library)
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(library_copy, f, indent=4)
        except (OSError, IOError, TypeError):
            pass

    invalidate_library_cache()
    return {"status": "success", "moved": moved, "count": len(moved)}


@router.get("/library/folders")
@router.get("/folders")
async def get_library_folders():
    """Returns all subfolders on disk in download and nomusic directories, including empty ones."""
    def scan_subdirs(base_dir):
        if not os.path.exists(base_dir):
            return []
        subdirs = []
        try:
            for entry in os.scandir(base_dir):
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry.name)
        except (OSError, PermissionError):
            pass
        return sorted(subdirs, key=lambda s: s.lower())

    return {
        "download": scan_subdirs(DOWNLOAD_DIR),
        "nomusic": scan_subdirs(NOMUSIC_DIR)
    }


@router.post("/library/create-folder")
async def create_folder(payload: dict):
    """Create a new subfolder in download or nomusic directory."""
    category = payload.get("category", "download")
    # Only allow known top-level categories to prevent path traversal via category
    if category not in ("download", "nomusic", "uploads", "projects"):
        raise HTTPException(status_code=400, detail="Invalid category")

    # Map category names to absolute paths
    category_paths = {
        "download": DOWNLOAD_DIR,
        "nomusic": NOMUSIC_DIR,
        "uploads": os.path.abspath("uploads"),
        "projects": os.path.abspath("projects"),
    }
    base_dir = category_paths.get(category, os.path.abspath(category))

    folder_name = payload.get("folder_name", "").strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Folder name is required")

    clean_name = os.path.basename(folder_name)
    target_path = os.path.join(base_dir, clean_name)

    if not is_path_within_allowed_roots(target_path, ALLOWED_ROOTS + [os.path.abspath(".")]):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")

    os.makedirs(target_path, exist_ok=True)
    invalidate_library_cache()
    return {"status": "created", "path": target_path, "name": clean_name}


@router.get("/media/stream")
@router.get("/stream-audio")
async def stream_media(path: str, request: Request = None):
    """Stream audio or video files directly to the browser for in-app playback with HTTP Range support."""
    import urllib.parse

    client_ip = request.client.host if request and request.client else "unknown"
    log_console(f"Stream request: {path[:120]} (from {client_ip})", "info")

    if not path:
        raise HTTPException(status_code=400, detail="Path parameter is required")

    # Clean up and normalize path (handle file:// prefix, urlencoded strings, etc.)
    path_str = urllib.parse.unquote(path).strip().strip('"').strip("'")
    if path_str.startswith("file:///"):
        path_str = path_str[8:]
    elif path_str.startswith("file://"):
        path_str = path_str[7:]

    clean_path = os.path.abspath(os.path.normpath(path_str))

    # If file doesn't exist directly, check relative to project root or nomusic/download
    if not os.path.exists(clean_path) or not os.path.isfile(clean_path):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        rel_path = os.path.abspath(os.path.join(project_root, path_str))
        if os.path.exists(rel_path) and os.path.isfile(rel_path):
            clean_path = rel_path
        else:
            raise HTTPException(status_code=404, detail=f"Media file not found: {clean_path}")

    # SECURITY: reject any path that escapes the allowed media roots
    if not is_path_within_allowed_roots(clean_path, ALLOWED_ROOTS + [os.path.abspath(".")]):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")

    ext = os.path.splitext(clean_path)[1].lower()
    media_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.m4a': 'audio/mp4',
        '.aac': 'audio/aac',
        '.ogg': 'audio/ogg',
        '.opus': 'audio/opus',
        '.flac': 'audio/flac',
        '.webm': 'audio/webm',
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
    }
    media_type = media_types.get(ext, 'audio/mpeg')
    filename = os.path.basename(clean_path)
    encoded_filename = urllib.parse.quote(filename)

    return FileResponse(
        path=clean_path,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length, Content-Type",
        }
    )


@router.post("/open-file")
async def open_file(payload: dict):
    """Open a file with default application."""
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    clean = os.path.abspath(os.path.normpath(path))
    if not os.path.exists(clean) or not os.path.isfile(clean):
        raise HTTPException(status_code=404, detail="File not found")

    if not is_path_within_allowed_roots(clean, ALLOWED_ROOTS + [os.path.abspath(".")]):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")

    try:
        if os.name == 'nt':  # Windows
            os.startfile(clean)
        elif os.name == 'posix':  # macOS/Linux
            subprocess.run(['open', clean] if os.uname().sysname == 'Darwin' else ['xdg-open', clean])
        return {"status": "opened", "path": clean}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {str(e)}")


@router.post("/open-folder")
async def open_folder(payload: dict):
    """Open a folder in file explorer."""
    path = payload.get("path")

    if not path:
        raise HTTPException(status_code=400, detail="Path required")

    # Resolve relative paths against allowed roots, not arbitrary parents
    if not os.path.isabs(path):
        path = os.path.join(os.path.abspath("."), path)
    path = os.path.abspath(os.path.normpath(path))

    # If the path points to a file, we want to open its parent directory
    if os.path.exists(path) and os.path.isfile(path):
        path = os.path.dirname(path)

    if not is_path_within_allowed_roots(path, ALLOWED_ROOTS + [os.path.abspath(".")]):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")

    if not os.path.exists(path):
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

        # Keep the in-memory tasks dict in sync so any task referencing the
        # old task_id/path (e.g. still-open UI state) doesn't go stale.
        old_task = tasks.pop(task_id, None)
        if old_task is not None:
            old_task["task_id"] = new_task_id
            old_task["result_files"] = [new_path]
            old_task["filename"] = os.path.basename(new_path)
            tasks[new_task_id] = old_task
            from services.persistence import save_tasks_sync
            save_tasks_sync()

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
