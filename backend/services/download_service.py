"""
Download service - handles downloads via yt-dlp (YouTube, Facebook, and more).
"""
import os
import sys
import time
import asyncio
from typing import Optional
from colorama import Fore, Style

# Ensure backend/modules is in sys.path for intra-module imports
_modules_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'modules'))
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)

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
    """Download video/audio from any yt-dlp supported platform."""
    import yt_dlp

    print(f"\n{Fore.CYAN}[Downloader] >>> Starting run_yt_dlp for task {task_id[:8]}... URL: {url} | Format: {format_type}{Style.RESET_ALL}")
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

    from core.constants import DOWNLOAD_DIR

    # Build output directory (optionally inside a subfolder)
    if subfolder:
        # Sanitize subfolder name to prevent path traversal and strip channel @ prefix
        import re
        safe_subfolder = re.sub(r'[\\/:*?"<>|]', '_', subfolder).lstrip('@').strip('. ')
        output_dir = os.path.join(DOWNLOAD_DIR, safe_subfolder)
    else:
        output_dir = DOWNLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)
    log_console(f"Output directory: {os.path.abspath(output_dir)}", "info")

    progress_state = {"progress": 5, "current_step": "Fetching video info...", "last_saved_threshold": 0}

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
                # Periodically save (roughly every 20% crossed, not just exact multiples)
                threshold = (int(progress) // 20) * 20
                if threshold > progress_state["last_saved_threshold"]:
                    progress_state["last_saved_threshold"] = threshold
                    from services.persistence import save_tasks_sync
                    save_tasks_sync()
        elif d.get('status') == 'finished':
            progress_state["progress"] = 90
            progress_state["current_step"] = "Processing file..."
            tasks[task_id]["progress"] = 90
            tasks[task_id]["current_step"] = progress_state["current_step"]
            log_console("Download finished, processing...", "info")

    class YTDLPLogger:
        def debug(self, msg):
            # Strip noisy progress debug lines from filling logs
            if not msg.startswith('[debug] ') and not msg.startswith('[download]'):
                pass

        def info(self, msg):
            pass

        def warning(self, msg):
            print(f"{Fore.YELLOW}[yt-dlp:warning] {msg}{Style.RESET_ALL}")
            log_console(f"[yt-dlp warning] {msg}", "warning")

        def error(self, msg):
            print(f"{Fore.RED}[yt-dlp:error] {msg}{Style.RESET_ALL}")
            log_console(f"[yt-dlp error] {msg}", "error")

    def get_ydl_opts():
        cookies_path = os.path.join("data", "cookies.txt")
        from modules.module_ffmpeg import FFMPEG_EXE
        ffmpeg_dir = os.path.dirname(FFMPEG_EXE) if os.path.exists(FFMPEG_EXE) else None

        opts = {
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'logger': YTDLPLogger(),
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            # Download DASH/HLS fragments in parallel
            'concurrent_fragment_downloads': 4,
        }

        if ffmpeg_dir:
            opts['ffmpeg_location'] = ffmpeg_dir

        if os.path.exists(cookies_path):
            opts['cookiefile'] = cookies_path

        if format_type == 'audio':
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
            if format_id and format_id != 'best':
                opts['format'] = f"{format_id}/bestaudio/best"
        else:
            if format_id:
                opts['format'] = f"{format_id}+bestaudio/best"
            else:
                opts['format'] = 'bestvideo+bestaudio/best'

        if subtitles:
            opts['writesubtitles'] = True
            opts['subtitleslangs'] = [subtitles]
            opts['writeautomaticsub'] = True
            
        return opts

    try:
        task_start_time = time.time()
        ydl_opts = get_ydl_opts()
        success = False
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            active_downloads[task_id]["ydl"] = ydl
            tasks[task_id]["current_step"] = "Extracting video info..."
            tasks[task_id]["progress"] = 10
            info = ydl.extract_info(url, download=True)
            success = True

            if active_downloads.get(task_id, {}).get("cancel_flag", False):
                raise Exception("Download cancelled by user")
            
            if info is None:
                raise Exception("Download failed or was aborted by yt-dlp (info missing)")

            video_title = info.get('title', 'Unknown')
            log_prefix = f"[{video_title[:40]}]" if video_title != 'Unknown' else f"[{task_id[:8]}]"
            log_console(f"{log_prefix} Extraction complete", "info")
            tasks[task_id]["current_step"] = "Starting download..."
            tasks[task_id]["progress"] = 15
            log_console(f"{log_prefix} Starting download, progress=15%", "info")
            
            # Determine actual output file accurately
            actual_filename = None
            req_downloads = info.get('requested_downloads') or []
            for rd in req_downloads:
                rd_path = rd.get('filepath') or rd.get('_filename')
                if rd_path and os.path.exists(rd_path):
                    actual_filename = rd_path
                    break

            if not actual_filename or not os.path.exists(actual_filename):
                filename = ydl.prepare_filename(info)
                if format_type == 'audio':
                    base = os.path.splitext(filename)[0]
                    filename = f"{base}.mp3"
                if os.path.exists(filename):
                    actual_filename = filename
                else:
                    base_no_ext = os.path.splitext(filename)[0]
                    for try_ext in ['.mp3', '.m4a', '.mp4', '.mkv', '.webm', '.wav', '.opus']:
                        candidate = base_no_ext + try_ext
                        if os.path.exists(candidate):
                            actual_filename = candidate
                            break

            if not actual_filename or not os.path.exists(actual_filename):
                media_exts = {'.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.opus'}
                candidates = []
                for f in os.listdir(output_dir):
                    fpath = os.path.join(output_dir, f)
                    if os.path.isfile(fpath) and os.path.splitext(f)[1].lower() in media_exts:
                        mtime = os.path.getmtime(fpath)
                        if mtime >= task_start_time - 10:
                            candidates.append((mtime, fpath))
                if candidates:
                    candidates.sort(reverse=True)
                    actual_filename = candidates[0][1]

            if not actual_filename or not os.path.exists(actual_filename):
                raise Exception("Downloaded file could not be found on disk")
                    
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

                # Save initial download to library with file metadata
                library_entry = {
                    "task_id": task_id,
                    "url": url,
                    "title": info.get('title', 'Unknown'),
                    "result_files": [filename],
                    "download_info": tasks[task_id]["download_info"],
                    "metadata": file_metadata,
                    "status": "completed",
                    "format": format_type,
                    "model": "both" if auto_separate else None
                }
                save_to_library(library_entry)
                get_full_library()

                if not auto_separate:
                    add_notification(
                        "success",
                        "Download Complete",
                        f"{info.get('title', 'Unknown')} downloaded successfully",
                        {"task_id": task_id, "file": filename}
                    )
                else:
                    # Auto-separate if requested
                    log_console(f"Starting auto-separation for {filename}", "info")
                    tasks[task_id]["status"] = "processing"
                    tasks[task_id]["current_step"] = "Starting vocal separation..."
                    tasks[task_id]["progress"] = 50
                    from services.persistence import save_tasks_sync
                    save_tasks_sync()

                    from modules.module_processor import process_file
                    from modules.module_ffmpeg import download_ffmpeg

                    if not download_ffmpeg():
                        log_console("FFmpeg not available, skipping auto-separation", "warning")
                        tasks[task_id]["current_step"] = "Download complete (FFmpeg not available for separation)"
                        tasks[task_id]["status"] = "completed"
                        tasks[task_id]["progress"] = 100
                        save_tasks_sync()
                        add_notification(
                            "warning",
                            "Download Complete (Separation Skipped)",
                            f"{info.get('title', 'Unknown')} downloaded, but FFmpeg is not available.",
                            {"task_id": task_id, "file": filename}
                        )
                    else:
                        def on_sep_progress(step, progress):
                            if task_id in tasks:
                                # Map separation progress (0-100) to overall task progress (50-100)
                                overall_progress = 50 + int(progress * 0.5)
                                tasks[task_id]["current_step"] = f"Separating: {step}"
                                tasks[task_id]["progress"] = overall_progress
                                if int(overall_progress) % 10 == 0:
                                    save_tasks_sync()

                        success_result, phase_timings, instrumental_path = process_file(
                            filename,
                            keep_temp=False,
                            progress_callback=on_sep_progress,
                            model="both"
                        )

                        if success_result:
                            log_console(f"Auto-separation completed for {filename}", "success")
                            tasks[task_id]["status"] = "completed"
                            tasks[task_id]["progress"] = 100
                            tasks[task_id]["current_step"] = "Separation complete"
                            tasks[task_id]["timings"] = phase_timings

                            # Discover generated separated files in nomusic/ folder
                            from core.constants import NOMUSIC_DIR
                            output_dir = NOMUSIC_DIR
                            raw_name = os.path.basename(filename)
                            clean_name_base = os.path.splitext(raw_name)[0]

                            result_files = []
                            if os.path.exists(output_dir):
                                for f in os.listdir(output_dir):
                                    if clean_name_base in f and f != raw_name:
                                        result_files.append(os.path.join(output_dir, f))

                            if not result_files and isinstance(success_result, str):
                                result_files = [success_result]

                            tasks[task_id]["result_files"] = result_files
                            if instrumental_path:
                                tasks[task_id]["instrumental_file"] = instrumental_path

                            # Update library entry with separated outputs
                            library_entry["result_files"] = result_files
                            if result_files:
                                from config import get_file_metadata_cached
                                library_entry["metadata"] = get_file_metadata_cached(result_files[0])
                            save_to_library(library_entry)
                            get_full_library()

                            add_notification(
                                "success",
                                "Auto-Separation Complete",
                                f"{info.get('title', 'Unknown')} vocals separated successfully",
                                {"task_id": task_id, "files": result_files}
                            )
                            save_tasks_sync()
                        else:
                            log_console(f"Auto-separation failed for {filename}", "error")
                            tasks[task_id]["current_step"] = "Separation failed (download succeeded)"
                            tasks[task_id]["status"] = "completed"
                            tasks[task_id]["progress"] = 100
                            save_tasks_sync()
                            add_notification(
                                "error",
                                "Auto-Separation Failed",
                                f"Download finished, but separation encountered an error for {info.get('title', 'Unknown')}",
                                {"task_id": task_id, "file": filename}
                            )
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["current_step"] = "Download failed - file not found"
                add_notification("error", "Download Failed", f"Could not find downloaded file: {filename}")

    except Exception as e:
        import traceback
        traceback.print_exc()
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
        from services.persistence import save_tasks_sync
        save_tasks_sync()
    finally:
        active_downloads.pop(task_id, None)
