import os
import sys
import json
import subprocess
import time
import shutil
import asyncio
import importlib.metadata
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException

import torch
import psutil

from config import (
    console_logs, notifications, MAX_LOGS, MAX_NOTIFICATIONS,
    save_notifications, tasks, get_full_library
)

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications")
async def get_notifications():
    """Get all notifications."""
    unread_count = sum(1 for n in notifications if not n.get("read", False))
    return {"notifications": notifications, "unread_count": unread_count}


@router.post("/notifications/test")
async def test_notification():
    """Send a test notification."""
    import uuid
    
    notification = {
        "id": str(uuid.uuid4()),
        "type": "info",
        "title": "Test Notification",
        "message": "This is a test notification from the backend",
        "read": False,
        "created_at": time.time()
    }
    notifications.insert(0, notification)
    notifications[:] = notifications[:MAX_NOTIFICATIONS]
    save_notifications()
    
    return {"status": "sent", "notification": notification}


@router.post("/notifications/mark-read")
async def mark_all_read():
    """Mark all notifications as read."""
    for n in notifications:
        n["read"] = True
    save_notifications()
    return {"status": "ok"}


@router.post("/notifications/mark-single-read")
async def mark_single_read(payload: dict):
    """Mark a single notification as read."""
    notif_id = payload.get("id")
    for n in notifications:
        if n["id"] == notif_id:
            n["read"] = True
            break
    save_notifications()
    return {"status": "ok"}


@router.post("/notifications/clear")
async def clear_notifications():
    """Clear all notifications."""
    notifications.clear()
    save_notifications()
    return {"status": "cleared"}


@router.get("/console-logs")
async def get_console_logs():
    """Get recent console logs for frontend display."""
    recent_logs = console_logs[-100:] if len(console_logs) > 100 else console_logs
    return {
        "logs": list(reversed(recent_logs)),
        "count": len(recent_logs)
    }


@router.post("/console-logs/clear")
async def clear_console_logs():
    """Clear all console logs."""
    global console_logs
    console_logs = []
    return {"status": "cleared"}


# --- OPTIMIZATION: Caching and Parallelism ---
# Cache for system info to avoid expensive calculations every time
_system_info_cache = {"data": None, "expiry": 0}
SYSTEM_INFO_CACHE_TTL = 300  # 5 minutes

# Static info cache (rarely/never changes)
_static_info = None
_diag_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="sysinfo")

def get_static_info():
    """Gather info that doesn't change: package versions, python version, GPU specs."""
    global _static_info
    if _static_info:
        return _static_info

    info = {
        "packages": {
            "python": sys.version.split()[0],
            "yt-dlp": "N/A",
            "demucs": "N/A",
            "spleeter": "N/A",
            "pytorch": torch.__version__,
            "torchaudio": "N/A",
            "ffmpeg": "N/A",
            "fdk_aac": False
        },
        "gpu": {
            "available": False,
            "name": "N/A",
            "vram_total": "N/A",
            "cuda_version": "N/A"
        }
    }

    # Packages
    for pkg in ["yt-dlp", "demucs", "spleeter", "torchaudio"]:
        try:
            info["packages"][pkg] = importlib.metadata.version(pkg)
        except Exception:
            pass

    # FFmpeg
    try:
        from modules.module_ffmpeg import get_ffmpeg_version, check_fdk_aac_codec
        info["packages"]["ffmpeg"] = get_ffmpeg_version()
        info["packages"]["fdk_aac"] = check_fdk_aac_codec()
    except Exception:
        pass

    # GPU
    try:
        if torch.cuda.is_available():
            info["gpu"]["available"] = True
            info["gpu"]["name"] = torch.cuda.get_device_name(0)
            info["gpu"]["cuda_version"] = torch.version.cuda
            total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            info["gpu"]["vram_total"] = f"{total_vram:.1f} GB"
    except Exception:
        pass

    _static_info = info
    return info

def get_folder_size(folder):
    """Calculate total size of a folder (expensive)."""
    total = 0
    if os.path.exists(folder):
        for root, dirs, files in os.walk(folder):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except (OSError, IOError):
                    pass
    return total

def get_library_stats():
    """Calculate library size (expensive)."""
    library = get_full_library()
    total_files = len(library)
    total_size_bytes = 0
    for item in library:
        for f in item.get("result_files", []):
            try:
                if os.path.exists(f):
                    total_size_bytes += os.path.getsize(f)
            except (OSError, IOError):
                pass
    return {
        "total_files": total_files,
        "total_size": f"{total_size_bytes / (1024**2):.1f} MB"
    }

def get_dynamic_info():
    """Gather info that changes frequently but is fast to get: RAM, Disk free."""
    info = {
        "memory": {"total": "N/A", "available": "N/A", "demucs_usage": "~8GB per job"},
        "storage": {"total": "N/A", "free": "N/A"}
    }
    try:
        mem = psutil.virtual_memory()
        info["memory"]["total"] = f"{mem.total / (1024**3):.1f} GB"
        info["memory"]["available"] = f"{mem.available / (1024**3):.1f} GB"
        
        disk = psutil.disk_usage(os.path.abspath("."))
        info["storage"]["total"] = f"{disk.total / (1024**3):.1f} GB"
        info["storage"]["free"] = f"{disk.free / (1024**3):.1f} GB"
    except Exception:
        pass
    return info

@router.get("/system-info")
async def get_system_info():
    """Get system information with optimized gathering and caching."""
    global _system_info_cache
    
    now = time.time()
    if _system_info_cache["data"] and now < _system_info_cache["expiry"]:
        return _system_info_cache["data"]

    # Start independent tasks concurrently
    loop = asyncio.get_event_loop()
    
    # 1. Static and Dynamic info (fast)
    static_info_task = loop.run_in_executor(_diag_executor, get_static_info)
    dynamic_info_task = loop.run_in_executor(_diag_executor, get_dynamic_info)
    
    # 2. Folder sizes and Library stats (slow)
    nomusic_size_task = loop.run_in_executor(_diag_executor, get_folder_size, "nomusic")
    download_size_task = loop.run_in_executor(_diag_executor, get_folder_size, "download")
    library_stats_task = loop.run_in_executor(_diag_executor, get_library_stats)

    # Wait for everything
    static_info, dynamic_info, nomusic_size, download_size, library_stats = await asyncio.gather(
        static_info_task, dynamic_info_task, nomusic_size_task, download_size_task, library_stats_task
    )

    # Assemble final object
    info = {
        **static_info,
        **dynamic_info,
        "processing": {
            "demucs_workers": 2,
            "segment_duration": "600s"
        },
        "storage": {
            **dynamic_info["storage"],
            "output_folder": os.path.abspath("nomusic"),
            "download_folder": os.path.abspath("download"),
            "output_size": f"{nomusic_size / (1024**2):.1f} MB",
            "download_size": f"{download_size / (1024**2):.1f} MB"
        },
        "library": library_stats
    }

    _system_info_cache = {
        "data": info,
        "expiry": time.time() + SYSTEM_INFO_CACHE_TTL
    }
    return info


@router.get("/deno-info")
async def get_deno_info():
    """Get Deno version and status."""
    import asyncio

    def check_deno():
        try:
            result = subprocess.run(["deno", "--version"], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                return {"available": True, "version": result.stdout.split('\n')[0]}
        except (subprocess.SubprocessError, OSError):
            pass
        return {"available": False, "version": "Not installed"}

    return await asyncio.to_thread(check_deno)
