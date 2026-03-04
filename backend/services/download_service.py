"""
Download service - handles YouTube downloads via yt-dlp.
"""
import os
import asyncio
from typing import Optional
from colorama import Fore, Style

from config import (
    tasks, active_downloads, save_to_library, add_notification,
    log_console, download_queue, save_queue, get_full_library
)
from utils.helpers import format_duration


def run_yt_dlp(
    task_id: str,
    url: str,
    format_type: str = 'audio',
    format_id: str = None,
    subtitles: str = None,
    auto_separate: bool = False,
    subfolder: str = None
):
    """Download video/audio from YouTube using yt-dlp."""
    import yt_dlp
    from yt_dlp.networking.impersonate import ImpersonateTarget

    tasks[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "progress": 5,
        "current_step": "Fetching video info...",
        "result_files": [],
        "url": url,
        "type": "download"
    }

    active_downloads[task_id] = {"cancel_flag": False, "ydl": None}

    # Build output directory (optionally inside a subfolder)
    if subfolder:
        # Sanitize subfolder name to prevent path traversal and strip channel @ prefix
        import re
        safe_subfolder = re.sub(r'[\\/:*?"<>|]', '_', subfolder).lstrip('@').strip('. ')
        output_dir = os.path.join("download", safe_subfolder)
    else:
        output_dir = "download"
    os.makedirs(output_dir, exist_ok=True)
    log_console(f"Output directory: {os.path.abspath(output_dir)}", "info")

    progress_state = {"progress": 5, "current_step": "Fetching video info..."}

    def progress_hook(d):
        if active_downloads.get(task_id, {}).get("cancel_flag", False):
            raise Exception("Download cancelled by user")

        if d.get('status') == 'downloading':
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            
            if total_bytes and downloaded_bytes:
                progress = (downloaded_bytes / total_bytes) * 100
                # Scale progress from 10% to 90% to leave room for post-processing
                scaled_progress = 10 + (progress * 0.8)
                progress_state["progress"] = scaled_progress
                
                # Build detailed status info
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                speed_str = "N/A"
                if speed:
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                    elif speed > 1024:
                        speed_str = f"{speed / 1024:.1f} KB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"
                
                eta_str = "N/A"
                if eta:
                    eta_min = int(eta) // 60
                    eta_sec = int(eta) % 60
                    eta_str = f"{eta_min}:{eta_sec:02d}"
                
                info_dict = d.get('info_dict') or {}
                playlist_index = info_dict.get('playlist_index')
                playlist_count = info_dict.get('playlist_count') or info_dict.get('n_entries')
                raw_filename = d.get('filename', '') or ''
                # Strip .part extension shown during partial downloads
                clean_filename = os.path.basename(raw_filename)
                if clean_filename.endswith('.part'):
                    clean_filename = clean_filename[:-5]
                
                progress_state["current_step"] = f"Downloading... {progress:.1f}%"
                tasks[task_id]["progress"] = scaled_progress
                tasks[task_id]["current_step"] = progress_state["current_step"]
                tasks[task_id]["download_info"] = {
                    "speed": speed_str,
                    "eta": eta_str,
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                    "progress": progress,
                    "playlist_index": playlist_index,
                    "playlist_count": playlist_count,
                    "filename": clean_filename
                }
                # Periodically save (every 20%)
                if int(progress) % 20 == 0:
                    from services.persistence import save_tasks_sync
                    save_tasks_sync()
        elif d.get('status') == 'finished':
            progress_state["progress"] = 90
            progress_state["current_step"] = "Processing file..."
            tasks[task_id]["progress"] = 90
            tasks[task_id]["current_step"] = progress_state["current_step"]
            log_console("Download finished, processing...", "info")

    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': False,  # Changed to False to ensure progress hooks work
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': True,  # CRITICAL: Only download the single video, not the entire playlist
        'remote_components': ['ejs:github'],
        'impersonate': ImpersonateTarget(client='chrome'),
    }

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        })
        if format_id and format_id != 'best':
            ydl_opts['format'] = f"{format_id}+bestaudio/bestaudio"
    else:
        if format_id:
            ydl_opts['format'] = f"{format_id}+bestaudio/best"
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'

    if subtitles:
        ydl_opts['writesubtitles'] = True
        ydl_opts['subtitleslangs'] = [subtitles]
        ydl_opts['writeautomaticsub'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            active_downloads[task_id]["ydl"] = ydl
            
            # Update status before extraction
            tasks[task_id]["current_step"] = "Extracting video info..."
            tasks[task_id]["progress"] = 10
            log_console(f"Task {task_id}: Starting extraction, progress=10%", "info")
            
            info = ydl.extract_info(url, download=True)
            
            if active_downloads.get(task_id, {}).get("cancel_flag", False):
                raise Exception("Download cancelled by user")
            
            if info is None:
                raise Exception("Download failed or was aborted by yt-dlp (info missing)")

            log_console(f"Task {task_id}: Extraction complete, title={info.get('title', 'Unknown')}", "info")
            tasks[task_id]["current_step"] = "Starting download..."
            tasks[task_id]["progress"] = 15
            log_console(f"Task {task_id}: Starting download, progress=15%", "info")
            
            filename = ydl.prepare_filename(info)

            # Handle audio conversion result
            if format_type == 'audio':
                base = os.path.splitext(filename)[0]
                filename = f"{base}.mp3"
                tasks[task_id]["current_step"] = "Converting to MP3..."

            # Determine actual output file - yt-dlp may merge to a different ext
            # e.g. prepare_filename gives .webm but merged output is .mp4
            actual_filename = filename
            if not os.path.exists(actual_filename):
                base_no_ext = os.path.splitext(filename)[0]
                # Try common merged extensions
                for try_ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                    candidate = base_no_ext + try_ext
                    if os.path.exists(candidate):
                        actual_filename = candidate
                        break
                else:
                    # Last resort: find the most recently modified media file in output_dir
                    media_exts = {'.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac'}
                    candidates = []
                    for f in os.listdir(output_dir):
                        fpath = os.path.join(output_dir, f)
                        if os.path.isfile(fpath) and os.path.splitext(f)[1].lower() in media_exts:
                            candidates.append((os.path.getmtime(fpath), fpath))
                    if candidates:
                        candidates.sort(reverse=True)
                        actual_filename = candidates[0][1]
                    
            if os.path.exists(actual_filename):
                filename = actual_filename
                tasks[task_id]["progress"] = 95
                tasks[task_id]["current_step"] = "Extracting metadata..."

                # Extract actual file metadata using ffprobe
                from modules.module_ffmpeg import get_file_metadata
                file_metadata = get_file_metadata(filename)

                tasks[task_id]["result_files"] = [filename]
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["progress"] = 100
                tasks[task_id]["current_step"] = "Download complete"
                tasks[task_id]["metadata"] = file_metadata
                tasks[task_id]["download_info"] = {
                    "title": info.get('title', 'Unknown'),
                    "duration": info.get('duration', 0),
                    "thumbnail": info.get('thumbnail', '')
                }
                from services.persistence import save_tasks_sync
                save_tasks_sync()

                # Save to library with actual file metadata
                library_entry = {
                    "task_id": task_id,
                    "url": url,
                    "title": info.get('title', 'Unknown'),
                    "result_files": [filename],
                    "download_info": tasks[task_id]["download_info"],
                    "metadata": file_metadata,
                    "status": "completed",
                    "format": format_type
                }
                save_to_library(library_entry)

                # Refresh library to ensure UI gets updated data
                get_full_library()

                add_notification(
                    "success",
                    "Download Complete",
                    f"{info.get('title', 'Unknown')} downloaded successfully",
                    {"task_id": task_id, "file": filename}
                )

                # Auto-separate if requested
                if auto_separate:
                    log_console(f"Starting auto-separation for {filename}", "info")
                    tasks[task_id]["current_step"] = "Starting vocal separation..."
                    tasks[task_id]["progress"] = 50
                    from modules.module_processor import process_file
                    from modules.module_ffmpeg import download_ffmpeg

                    if download_ffmpeg():
                        process_file(filename, keep_temp=False)
                        log_console(f"Auto-separation completed for {filename}", "success")
                        tasks[task_id]["progress"] = 100
                        tasks[task_id]["current_step"] = "Separation complete"
                    else:
                        log_console("FFmpeg not available, skipping auto-separation", "warning")
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["current_step"] = "Download failed - file not found"
                add_notification("error", "Download Failed", f"Could not find downloaded file: {filename}")

    except Exception as e:
        error_msg = str(e)
        if "cancelled" in error_msg.lower():
            tasks[task_id]["status"] = "cancelled"
            tasks[task_id]["current_step"] = "Download cancelled by user"
            add_notification("info", "Download Cancelled", f"task_id: {task_id}")
        else:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = f"Error: {error_msg[:100]}"
            add_notification("error", "Download Failed", error_msg[:200])
        log_console(f"Download error for {url}: {error_msg}", "error")
    finally:
        active_downloads.pop(task_id, None)
