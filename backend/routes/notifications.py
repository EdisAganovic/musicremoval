"""
Notifications and System API Routes.
"""
import os
import sys
import json
import subprocess
import time
import shutil
from fastapi import APIRouter, HTTPException

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


# Cache for system info to avoid expensive subprocess calls every time
_system_info_cache = {"data": None, "expiry": 0}
SYSTEM_INFO_CACHE_TTL = 300  # 5 minutes

@router.get("/system-info")
async def get_system_info():
    """Get system information including GPU, CUDA, and package versions."""
    import torch
    import asyncio
    import time
    
    global _system_info_cache
    
    now = time.time()
    if _system_info_cache["data"] and now < _system_info_cache["expiry"]:
        return _system_info_cache["data"]

    def gather_info():
        info = {
            "gpu": {
                "available": False,
                "name": "N/A",
                "vram_total": "N/A",
                "vram_free": "N/A",
                "cuda_version": "N/A"
            },
            "packages": {
                "python": sys.version.split()[0],
                "yt-dlp": "N/A",
                "demucs": "N/A",
                "spleeter": "N/A",
                "pytorch": torch.__version__,
                "torchaudio": "N/A",
                "ffmpeg": "N/A"
            },
            "processing": {
                "demucs_workers": 2,
                "segment_duration": "600s"
            },
            "memory": {
                "total": "N/A",
                "available": "N/A",
                "demucs_usage": "~8GB per job"
            },
            "storage": {
                "total": "N/A",
                "free": "N/A",
                "output_folder": os.path.abspath("nomusic"),
                "download_folder": os.path.abspath("download"),
                "output_size": "0 MB",
                "download_size": "0 MB"
            },
            "library": {
                "total_files": 0,
                "total_size": "0 MB"
            }
        }

        # Check GPU
        if torch.cuda.is_available():
            info["gpu"]["available"] = True
            info["gpu"]["name"] = torch.cuda.get_device_name(0)
            info["gpu"]["cuda_version"] = torch.version.cuda

            try:
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                info["gpu"]["vram_total"] = f"{total_vram:.1f} GB"
            except (AttributeError, TypeError, OverflowError):
                pass

        # Get package versions
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", "yt-dlp"],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        info["packages"]["yt-dlp"] = line.split(':')[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass

        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", "demucs"],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        info["packages"]["demucs"] = line.split(':')[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass

        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", "spleeter"],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        info["packages"]["spleeter"] = line.split(':')[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass

        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", "torchaudio"],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        info["packages"]["torchaudio"] = line.split(':')[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass

        # Check FFmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            info["packages"]["ffmpeg"] = ffmpeg_path
            try:
                result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, encoding='utf-8', errors='replace')
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    info["packages"]["ffmpeg"] = version_line
            except (subprocess.SubprocessError, OSError):
                pass

        # Get memory info
        try:
            import psutil
            mem = psutil.virtual_memory()
            info["memory"]["total"] = f"{mem.total / (1024**3):.1f} GB"
            info["memory"]["available"] = f"{mem.available / (1024**3):.1f} GB"
        except (ImportError, AttributeError, TypeError):
            pass

        # Get storage info
        try:
            import psutil
            disk = psutil.disk_usage(os.path.abspath("."))
            info["storage"]["total"] = f"{disk.total / (1024**3):.1f} GB"
            info["storage"]["free"] = f"{disk.free / (1024**3):.1f} GB"
        except (ImportError, AttributeError, TypeError, OSError):
            pass

        # Calculate folder sizes
        def get_folder_size(folder):
            total = 0
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                        except (OSError, IOError):
                            pass
            return total

        output_size = get_folder_size("nomusic")
        download_size = get_folder_size("download")
        info["storage"]["output_size"] = f"{output_size / (1024**2):.1f} MB"
        info["storage"]["download_size"] = f"{download_size / (1024**2):.1f} MB"

        # Library stats
        library = get_full_library()
        info["library"]["total_files"] = len(library)
        library_size = sum(
            sum(os.path.getsize(f) for f in item.get("result_files", []) if os.path.exists(f))
            for item in library
        )
        info["library"]["total_size"] = f"{library_size / (1024**2):.1f} MB"

        return info

    info = await asyncio.to_thread(gather_info)
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
