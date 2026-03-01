import os
import sys
import uuid
import asyncio
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import json
import subprocess
from yt_dlp.networking.impersonate import ImpersonateTarget
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Add parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add modules directory to sys.path so that module_processor can import siblings
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules"))

from modules.module_processor import process_file
from modules.module_ffmpeg import get_file_metadata
from modules.module_deno import run_deno_script, deno_eval

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock task storage (use a DB or Redis for production)
tasks: Dict[str, dict] = {}
LIBRARY_FILE = "library.json"
QUEUE_FILE = "download_queue.json"
NOTIFICATIONS_FILE = "notifications.json"

# Download queue storage
download_queue: List[dict] = []
queue_lock = asyncio.Lock()
queue_processing = False

# Notifications storage
notifications: List[dict] = []
MAX_NOTIFICATIONS = 50

# Active downloads tracking for cancellation
active_downloads: Dict[str, dict] = {}  # task_id -> { "cancel_flag": bool, "ydl": YoutubeDL instance }

# Print notifications file path for debugging
print(f"[DEBUG] Notifications will be saved to: {os.path.abspath(NOTIFICATIONS_FILE)}")

class QueueItem(BaseModel):
    queue_id: str
    url: str
    format_type: str
    format_id: str = None
    subtitles: str = None
    auto_separate: bool = False
    status: str = "pending"  # pending, downloading, completed, failed
    task_id: str = None
    added_at: float = None

def save_to_library(task_data):
    """Saves a completed task to the local JSON library ✨."""
    try:
        library = []
        if os.path.exists(LIBRARY_FILE) and os.path.getsize(LIBRARY_FILE) > 0:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                try:
                    library = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: {LIBRARY_FILE} was corrupted. Starting fresh.")
                    library = []
        
        # Add new task at the beginning if not already there (prevent duplicates)
        # Check if task_id already exists in library
        existing_ids = {t.get("task_id") for t in library if isinstance(t, dict)}
        if task_data.get("task_id") not in existing_ids:
            library.insert(0, task_data)
        
        # Limit library size to 100 items
        library = library[:100]
        
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=4)
    except Exception as e:
        print(f"Error saving to library: {e}")

def get_full_library():
    """Reads all completed tasks and prunes missing files 🧼."""
    if not os.path.exists(LIBRARY_FILE) or os.path.getsize(LIBRARY_FILE) == 0:
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            library = json.load(f)
            
        # Filter out items where the primary result file no longer exists
        valid_items = []
        changed = False
        for item in library:
            res_files = item.get("result_files", [])
            if res_files and os.path.exists(res_files[0]):
                valid_items.append(item)
            else:
                changed = True
        
        # If any items were removed, update the JSON file
        if changed:
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(valid_items, f, indent=4)
            return valid_items
            
        return library
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"Error reading library: {e}")
        return []

def load_queue():
    """Loads the download queue from disk."""
    global download_queue
    if os.path.exists(QUEUE_FILE) and os.path.getsize(QUEUE_FILE) > 0:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                download_queue = json.load(f)
        except:
            download_queue = []

def save_queue():
    """Saves the download queue to disk."""
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(download_queue, f, indent=4)
    except Exception as e:
        print(f"Error saving queue: {e}")

def load_notifications():
    """Loads notifications from disk."""
    global notifications
    if os.path.exists(NOTIFICATIONS_FILE) and os.path.getsize(NOTIFICATIONS_FILE) > 0:
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)
        except:
            notifications = []

def save_notifications():
    """Saves notifications to disk."""
    try:
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(notifications, f, indent=4)
        print(f"[DEBUG] Saved {len(notifications)} notifications to {NOTIFICATIONS_FILE}")
    except Exception as e:
        print(f"Error saving notifications: {e}")
        import traceback
        traceback.print_exc()

def cleanup_temp_files():
    """Clean up temporary files older than 24 hours."""
    import time
    temp_dirs = ['_temp', 'uploads', 'spleeter_out', 'demucs_out', '_processing_intermediates']
    max_age_seconds = 24 * 60 * 60  # 24 hours
    current_time = time.time()
    cleaned_count = 0
    
    print(f"\n{Fore.CYAN}=== Cleaning up temporary files ==={Style.RESET_ALL}")
    
    for dir_name in temp_dirs:
        dir_path = os.path.join(os.path.dirname(__file__), '..', dir_name)
        if not os.path.exists(dir_path):
            continue
            
        try:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            cleaned_count += 1
                            print(f"  Deleted: {file} ({int(file_age/3600)}h old)")
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"  Error cleaning {dir_name}: {e}")
    
    if cleaned_count > 0:
        print(f"{Fore.GREEN}✓ Cleaned {cleaned_count} old files{Style.RESET_ALL}\n")
    else:
        print(f"  No old files to clean\n")

def add_notification(type: str, title: str, message: str, data: dict = None):
    """Adds a new notification."""
    import time
    notification = {
        "id": str(uuid.uuid4()),
        "type": type,  # success, error, warning, info
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": time.time()
    }
    notifications.insert(0, notification)
    # Limit notifications
    notifications[:] = notifications[:MAX_NOTIFICATIONS]
    save_notifications()
    print(f"[NOTIFICATION] {type.upper()}: {title} - {message}")

async def process_queue():
    """Process download queue items one by one."""
    global queue_processing, download_queue
    
    if queue_processing:
        return
    
    queue_processing = True
    
    while True:
        # Find next pending item
        pending_item = None
        for item in download_queue:
            if item.get("status") == "pending":
                pending_item = item
                break
        
        if not pending_item:
            break
        
        # Update item status to downloading
        pending_item["status"] = "downloading"
        save_queue()
        
        # Start download
        task_id = str(uuid.uuid4())
        pending_item["task_id"] = task_id
        
        # Run download
        await run_yt_dlp(
            task_id,
            pending_item["url"],
            pending_item.get("format_type", "audio"),
            pending_item.get("format_id"),
            pending_item.get("subtitles"),
            pending_item.get("auto_separate", False)
        )
        
        # Update queue item status based on task result
        task_status = tasks.get(task_id, {})
        if task_status.get("status") == "completed":
            pending_item["status"] = "completed"
        else:
            pending_item["status"] = "failed"
        
        save_queue()
        
        # Small delay between downloads
        await asyncio.sleep(2)
    
    queue_processing = False

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    current_step: str
    result_files: List[str] = []
    metadata: dict = {}

@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

async def run_yt_dlp(task_id: str, url: str, format_type: str = 'audio', format_id: str = None, subtitles: str = None, auto_separate: bool = False):
    tasks[task_id] = {"task_id": task_id, "status": "processing", "progress": 0, "current_step": "Starting download", "result_files": []}
    
    # Register this download as active
    active_downloads[task_id] = {"cancel_flag": False, "ydl": None}

    output_dir = "download"
    os.makedirs(output_dir, exist_ok=True)

    # Use shared dict for progress communication between thread and main loop
    progress_state = {"progress": 0, "current_step": "Starting download"}

    def progress_hook(d):
        # Check for cancellation
        if active_downloads.get(task_id, {}).get("cancel_flag", False):
            raise Exception("Download cancelled by user")
        
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%','').strip()
            try:
                progress_state["progress"] = float(p)
                tasks[task_id]["progress"] = float(p)
            except:
                pass
            # Show only percentage in status
            progress_state["current_step"] = f"Downloading: {p}%"
            tasks[task_id]["current_step"] = f"Downloading: {p}%"
            
        elif d['status'] == 'finished':
            progress_state["progress"] = 99
            tasks[task_id]["progress"] = 99
            tasks[task_id]["current_step"] = "Finalizing & Merging formats..."
            print(f"\n{Fore.GREEN}✓ Download finished, processing...{Style.RESET_ALL}")

    def download_worker():
        """Worker function to run yt-dlp in a thread pool"""
        # Use selected format_id if provided, otherwise fallback to defaults
        if format_id:
            download_format = f"{format_id}+bestaudio/best" if format_type == 'video' else format_id
        else:
            download_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if format_type == 'video' else 'bestaudio/best'

        ydl_opts = {
            'format': download_format,
            'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
            'progress_hooks': [progress_hook],
            'remote_components': ['ejs:github'],
            'quiet': True,
            'no_warnings': False,
            'impersonate': ImpersonateTarget(client='chrome'),
            'no_color': True,  # Disable color codes in output
        }

        if format_type == 'audio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        if subtitles and subtitles != "none":
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            if subtitles != "all":
                ydl_opts['subtitleslangs'] = [subtitles]
            else:
                ydl_opts['subtitleslangs'] = ['all']

            ydl_opts['sleep_subtitles'] = 60

            if format_type == 'video':
                ydl_opts['postprocessors'] = ydl_opts.get('postprocessors', []) + [{
                    'key': 'FFmpegEmbedSubtitle',
                }]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Store ydl instance for potential cancellation
            active_downloads[task_id]["ydl"] = ydl
            
            info = ydl.extract_info(url, download=True)

            final_filename = info.get('_filename')

            if not final_filename:
                final_filename = ydl.prepare_filename(info)

            if format_type == 'audio' and final_filename and not final_filename.endswith('.mp3'):
                final_filename = os.path.splitext(final_filename)[0] + ".mp3"

            if final_filename and not os.path.exists(final_filename):
                possible_name = ydl.prepare_filename(info)
                if not os.path.exists(possible_name):
                    title = info.get('title')
                    for f in os.listdir(output_dir):
                        if title in f and f.endswith(('.mp4', '.mp3', '.mkv', '.webm')):
                            final_filename = os.path.join(output_dir, f)
                            break
                else:
                    final_filename = possible_name

            if not final_filename:
                raise Exception("Could not determine final download filename.")

            return os.path.abspath(final_filename), info

    # Retry logic with exponential backoff
    max_retries = 3
    base_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Run blocking yt-dlp in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            final_filepath, info = await loop.run_in_executor(None, download_worker)
            break  # Success, exit retry loop
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff (2s, 4s, 8s...)
                delay = base_delay * (2 ** attempt)
                print(f"{Fore.YELLOW}Download failed (attempt {attempt + 1}/{max_retries}): {error_msg[:100]}")
                print(f"Retrying in {delay} seconds...{Style.RESET_ALL}")
                tasks[task_id]["current_step"] = f"Retry {attempt + 2}/{max_retries} in {delay}s..."
                await asyncio.sleep(delay)
            else:
                # Final attempt failed
                print(f"{Fore.RED}Download failed after {max_retries} attempts: {error_msg[:100]}{Style.RESET_ALL}")
                raise  # Re-raise to be handled by outer exception handler

    try:

        # Extract metadata for the library
        try:
            metadata = get_file_metadata(final_filepath)
            tasks[task_id]["metadata"] = metadata
        except Exception as meta_err:
            print(f"Error extracting metadata: {meta_err}")
            tasks[task_id]["metadata"] = {"duration": "N/A", "resolution": "N/A", "audio_codec": "N/A", "video_codec": "N/A", "is_video": format_type == 'video'}

        # If auto_separate is enabled, queue separation after download
        if auto_separate:
            print(f"Auto-separation enabled. Starting vocal separation for: {final_filepath}")
            tasks[task_id]["current_step"] = "Starting vocal separation..."
            tasks[task_id]["status"] = "separating"

            # Run separation
            try:
                separation_result = await loop.run_in_executor(None, process_file, final_filepath, False, None)

                if separation_result and isinstance(separation_result, str):
                    sep_abs_path = os.path.abspath(separation_result)
                    # Extract final metadata
                    try:
                        sep_metadata = get_file_metadata(sep_abs_path)
                        tasks[task_id]["metadata"] = sep_metadata
                    except Exception as meta_err:
                        print(f"Error extracting separation metadata: {meta_err}")

                    tasks[task_id]["status"] = "completed"
                    tasks[task_id]["progress"] = 100
                    tasks[task_id]["current_step"] = "Download & Separation Finished"
                    tasks[task_id]["result_files"] = [sep_abs_path]
                    save_to_library(tasks[task_id])
                    
                    # Send notification
                    filename = os.path.basename(sep_abs_path)
                    add_notification("success", "Download & Separation Complete", f"'{filename}' is ready in your library", {
                        "file_path": sep_abs_path,
                        "task_id": task_id
                    })
                    
                    print(f"Download and separation complete: {sep_abs_path}")
                    return
                else:
                    raise Exception("Separation failed")
            except Exception as sep_err:
                print(f"Separation error after download: {sep_err}")
                tasks[task_id]["current_step"] = f"Download OK, Separation failed: {str(sep_err)}"
                # Still save the downloaded file to library
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["progress"] = 100
                tasks[task_id]["result_files"] = [final_filepath]
                save_to_library(tasks[task_id])
                
                # Send notification for download only
                filename = os.path.basename(final_filepath)
                add_notification("warning", "Download Complete (Separation Failed)", f"'{filename}' downloaded but separation failed", {
                    "file_path": final_filepath,
                    "task_id": task_id,
                    "error": str(sep_err)
                })
                return

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result_files"] = [final_filepath]
        tasks[task_id]["current_step"] = "Finished"

        # Final library save with the correct merged filename
        save_to_library(tasks[task_id])
        
        # Send notification
        filename = os.path.basename(final_filepath)
        add_notification("success", "Download Complete", f"'{filename}' has been added to your library", {
            "file_path": final_filepath,
            "task_id": task_id
        })
        
        print(f"Download complete: {final_filepath}")

    except Exception as e:
        print(f"Download error: {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Download error: {str(e)}"

        # Send error notification
        add_notification("error", "Download Failed", f"Failed to download: {str(e)[:100]}", {
            "url": url,
            "task_id": task_id,
            "error": str(e)
        })
    finally:
        # Clean up active download tracking
        if task_id in active_downloads:
            del active_downloads[task_id]

@app.post("/api/yt-formats")
async def get_yt_formats(payload: dict):
    """Fetches available formats for a YouTube URL using yt-dlp -F logic ✨.
    Supports single videos, playlists, and channels."""
    url = payload.get("url")
    check_playlist = payload.get("check_playlist", False)
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        # First, check if it's a playlist/channel URL
        is_playlist_url = any(indicator in url for indicator in [
            '/playlist?', 'list=PL', 'list=UU', 'list=RD', 'list=LL',
            '/channel/', '/@', '/c/'
        ])
        
        if check_playlist and is_playlist_url:
            # Fetch playlist/channel info
            ydl_opts = {
                'quiet': True,
                'noplaylist': False,  # Allow playlist extraction
                'extract_flat': True,  # Don't download, just extract info
                'remote_components': ['ejs:github'],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extract playlist videos
                videos = []
                entries = info.get('entries', []) if info.get('_type') == 'playlist' else [info]
                
                for entry in entries:
                    if entry:  # Skip None entries (deleted/private videos)
                        videos.append({
                            "id": entry.get('id', ''),
                            "title": entry.get('title', 'Unknown'),
                            "thumbnail": entry.get('thumbnail', ''),
                            "duration": format_duration(entry.get('duration', 0)),
                            "url": entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id', '')}")
                        })
                
                return {
                    "is_playlist": True,
                    "title": info.get("title", "Playlist"),
                    "thumbnail": info.get("thumbnail", ""),
                    "video_count": len(videos),
                    "videos": videos
                }
        
        # Single video - get formats
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'remote_components': ['ejs:github'],
            'impersonate': ImpersonateTarget(client='chrome'),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                # Filter for useful information
                format_info = {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "note": f.get("format_note"),
                    "filesize": f.get("filesize"),
                    "url": f.get("url") # sometimes needed
                }
                # Simplify labels
                label = f"{f.get('ext')} - {f.get('resolution')} ({f.get('format_note') or ''})"
                if f.get('vcodec') == 'none':
                    label = f"Audio: {f.get('ext')} ({f.get('format_note') or ''})"
                format_info["label"] = label
                formats.append(format_info)

            # Extract available subtitles
            available_subs = []
            if 'subtitles' in info:
                for lang in info['subtitles']:
                    available_subs.append({"code": lang, "label": f"{lang} (Subtitle)"})
            if 'automatic_captions' in info:
                for lang in info['automatic_captions']:
                    # don't duplicate
                    if not any(s['code'] == lang for s in available_subs):
                        available_subs.append({"code": lang, "label": f"{lang} (Auto-generated)"})

            return {
                "is_playlist": False,
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "id": info.get("id"),
                "formats": formats,
                "subtitles": available_subs
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def format_duration(seconds):
    """Format duration in seconds to human readable string."""
    if not seconds:
        return "N/A"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    hours = minutes // 60
    if hours > 0:
        return f"{hours}:{minutes % 60:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

@app.post("/api/download")
async def download_video(background_tasks: BackgroundTasks, payload: dict):
    url = payload.get("url")
    format_type = payload.get("format", "audio")
    format_id = payload.get("format_id")
    subtitles = payload.get("subtitles")
    auto_separate = payload.get("auto_separate", False)
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Check for duplicates in library
    library = get_full_library()
    for item in library:
        # Check if URL or similar file already exists
        result_files = item.get("result_files", [])
        for res_file in result_files:
            # Simple duplicate check by filename
            if url.lower() in res_file.lower() or res_file.lower() in url.lower():
                return {
                    "status": "duplicate",
                    "message": "File already exists in library",
                    "existing_file": res_file,
                    "task_id": item.get("task_id")
                }

    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_yt_dlp, task_id, url, format_type, format_id, subtitles, auto_separate)
    return {"task_id": task_id}

@app.post("/api/queue/add")
async def add_to_queue(payload: dict):
    """Add a download to the queue."""
    url = payload.get("url")
    format_type = payload.get("format", "audio")
    format_id = payload.get("format_id")
    subtitles = payload.get("subtitles", "none")
    auto_separate = payload.get("auto_separate", False)
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    queue_item = {
        "queue_id": str(uuid.uuid4()),
        "url": url,
        "format_type": format_type,
        "format_id": format_id,
        "subtitles": subtitles,
        "auto_separate": auto_separate,
        "status": "pending",
        "task_id": None,
        "added_at": asyncio.get_event_loop().time()
    }
    
    download_queue.append(queue_item)
    save_queue()

    # Start queue processing if not already running
    asyncio.create_task(process_queue())

    return {"queue_id": queue_item["queue_id"], "status": "queued"}

@app.post("/api/queue/add-batch")
async def add_to_queue_batch(payload: dict):
    """Add multiple videos to the download queue (for playlists)."""
    videos = payload.get("videos", [])
    format_type = payload.get("format", "audio")
    format_id = payload.get("format_id")
    subtitles = payload.get("subtitles", "none")
    auto_separate = payload.get("auto_separate", False)

    if not videos:
        raise HTTPException(status_code=400, detail="No videos provided")

    added_count = 0
    for video in videos:
        url = video.get("url")
        if url:
            queue_item = {
                "queue_id": str(uuid.uuid4()),
                "url": url,
                "format_type": format_type,
                "format_id": format_id,
                "subtitles": subtitles,
                "auto_separate": auto_separate,
                "status": "pending",
                "task_id": None,
                "added_at": asyncio.get_event_loop().time(),
                "playlist_title": video.get("title", "")
            }
            download_queue.append(queue_item)
            added_count += 1
    
    save_queue()
    asyncio.create_task(process_queue())

    return {"added": added_count, "status": "queued"}

@app.get("/api/queue")
async def get_queue():
    """Get current download queue."""
    # Update queue items with latest task status
    for item in download_queue:
        if item.get("task_id") and item.get("status") == "downloading":
            task = tasks.get(item["task_id"], {})
            item["progress"] = task.get("progress", 0)
            item["current_step"] = task.get("current_step", "")
    
    return {"queue": download_queue, "processing": queue_processing}

@app.post("/api/queue/remove")
async def remove_from_queue(payload: dict):
    """Remove an item from the queue."""
    queue_id = payload.get("queue_id")
    
    global download_queue
    download_queue = [item for item in download_queue if item.get("queue_id") != queue_id]
    save_queue()
    
    return {"status": "removed"}

@app.post("/api/queue/clear")
async def clear_queue():
    """Clear all completed/failed items from the queue."""
    global download_queue
    download_queue = [item for item in download_queue if item.get("status") in ["pending", "downloading"]]
    save_queue()
    
    return {"status": "cleared"}

@app.post("/api/queue/start")
async def start_queue():
    """Manually start queue processing."""
    load_queue()
    asyncio.create_task(process_queue())
    return {"status": "started"}

@app.post("/api/queue/stop")
async def stop_queue():
    """Stop queue processing (will finish current download)."""
    global queue_processing
    queue_processing = False
    return {"status": "stopping"}

@app.get("/api/notifications")
async def get_notifications():
    """Get all notifications."""
    unread_count = sum(1 for n in notifications if not n.get("read", False))
    return {"notifications": notifications, "unread_count": unread_count}

@app.post("/api/notifications/test")
async def test_notification():
    """Send a test notification to verify the system works."""
    add_notification("info", "Test Notification", "This is a test notification from the server", {
        "test": True
    })
    return {"status": "ok", "message": "Test notification sent"}

@app.post("/api/notifications/mark-read")
async def mark_notifications_read(payload: dict = None):
    """Mark all notifications as read."""
    for notification in notifications:
        notification["read"] = True
    save_notifications()
    return {"status": "ok"}

@app.post("/api/notifications/mark-single-read")
async def mark_notification_read(payload: dict):
    """Mark a single notification as read."""
    notification_id = payload.get("id")
    for notification in notifications:
        if notification.get("id") == notification_id:
            notification["read"] = True
            break
    save_notifications()
    return {"status": "ok"}

@app.post("/api/notifications/clear")
async def clear_notifications():
    """Clear all notifications."""
    global notifications
    notifications = []
    save_notifications()
    return {"status": "ok"}

@app.post("/api/download/cancel")
async def cancel_download(payload: dict):
    """Cancel an active download by task_id."""
    task_id = payload.get("task_id")
    
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    
    if task_id not in active_downloads:
        # Check if task exists but isn't active
        if task_id in tasks:
            task_status = tasks[task_id].get("status", "")
            if task_status in ["completed", "failed"]:
                return {"status": "already_finished", "message": f"Download already {task_status}"}
        raise HTTPException(status_code=404, detail="Download not found or already finished")
    
    # Set cancel flag - the progress hook will check this
    active_downloads[task_id]["cancel_flag"] = True
    
    # Try to interrupt the ydl if available
    ydl = active_downloads[task_id].get("ydl")
    if ydl and hasattr(ydl, '_download_ytdl'):
        try:
            ydl.to_screen("\n\nDownload cancelled by user")
        except:
            pass
    
    # Update task status
    if task_id in tasks:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = "Cancelled by user"
        tasks[task_id]["progress"] = 0
    
    # Send notification
    add_notification("warning", "Download Cancelled", f"Download was stopped by user", {
        "task_id": task_id
    })
    
    print(f"\n{Fore.YELLOW}⚠ Download cancelled by user: {task_id}{Style.RESET_ALL}")
    
    return {"status": "cancelled", "task_id": task_id}

@app.post("/api/download/status")
async def get_download_status(payload: dict):
    """Get status of a specific download."""
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress"),
        "current_step": task.get("current_step"),
        "is_active": task_id in active_downloads
    }

@app.get("/api/downloads/active")
async def get_active_downloads():
    """Get all active downloads."""
    active = []
    for task_id in active_downloads:
        task = tasks.get(task_id, {})
        active.append({
            "task_id": task_id,
            "status": task.get("status"),
            "progress": task.get("progress"),
            "current_step": task.get("current_step")
        })
    return {"active_downloads": active}

async def run_separation(task_id: str, file_path: str, duration=None):
    def progress_callback(step, progress):
        tasks[task_id]["current_step"] = step
        tasks[task_id]["progress"] = progress
        tasks[task_id]["status"] = "processing"

    try:
        # Run process_file in a thread since it's blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_file, file_path, False, duration, progress_callback)

        if result and isinstance(result, str):
            abs_path = os.path.abspath(result)

            # Extract final metadata for the library
            try:
                metadata = get_file_metadata(abs_path)
                tasks[task_id]["metadata"] = metadata
            except Exception as meta_err:
                print(f"Error extracting separation metadata: {meta_err}")

            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Finished"
            tasks[task_id]["result_files"] = [abs_path]
            # Save to persistent library
            save_to_library(tasks[task_id])
            
            # Send success notification
            filename = os.path.basename(abs_path)
            add_notification("success", "Separation Complete", f"'{filename}' vocals are ready", {
                "file_path": abs_path,
                "task_id": task_id
            })
        elif result is False:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Processing failed or aborted"
            
            # Send failure notification
            filename = os.path.basename(file_path)
            add_notification("error", "Separation Failed", f"Failed to separate '{filename}'", {
                "file_path": file_path,
                "task_id": task_id
            })
        else:
            # Fallback for unexpected return types
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Internal error: Invalid processing result"
            
            # Send error notification
            add_notification("error", "Separation Error", f"Unexpected error during separation", {
                "file_path": file_path,
                "task_id": task_id
            })
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Error: {str(e)}"
        
        # Send error notification
        filename = os.path.basename(file_path)
        add_notification("error", "Separation Error", f"Error processing '{filename}': {str(e)[:100]}", {
            "file_path": file_path,
            "task_id": task_id,
            "error": str(e)
        })

@app.post("/api/separate")
async def separate_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())

    # Save uploaded file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Extract metadata
    metadata = get_file_metadata(file_path)

    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "current_step": "File uploaded",
        "result_files": [],
        "metadata": metadata
    }

    background_tasks.add_task(run_separation, task_id, file_path)

    return {"task_id": task_id, "metadata": metadata}

@app.post("/api/separate-file")
async def separate_file(background_tasks: BackgroundTasks, payload: dict):
    """Separate vocals from an existing file on the server (e.g., from library)."""
    file_path = payload.get("file_path")
    model = payload.get("model", "both")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    task_id = str(uuid.uuid4())
    
    # Extract metadata
    metadata = get_file_metadata(file_path)
    
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "current_step": "File queued for separation",
        "result_files": [],
        "metadata": metadata
    }
    
    background_tasks.add_task(run_separation, task_id, file_path)
    
    return {"task_id": task_id, "metadata": metadata}

@app.post("/api/separate-folder")
async def separate_folder(background_tasks: BackgroundTasks, payload: dict):
    """Separate vocals from all media files in a folder."""
    folder_path = payload.get("folder_path")
    model = payload.get("model", "both")
    duration = payload.get("duration")  # Optional duration limit
    
    if not folder_path or not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Supported extensions
    video_extensions = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.wmv')
    audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma')
    supported_extensions = video_extensions + audio_extensions
    
    # Find all media files
    media_files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(supported_extensions):
            media_files.append(os.path.join(folder_path, f))
    
    if not media_files:
        raise HTTPException(status_code=400, detail="No media files found in folder")
    
    # Create batch task
    batch_id = str(uuid.uuid4())
    batch_tasks = {
        "batch_id": batch_id,
        "folder": folder_path,
        "total_files": len(media_files),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }
    
    # Store batch info
    tasks[batch_id] = {
        "batch": True,
        **batch_tasks
    }
    
    # Process each file
    for file_path in media_files:
        task_id = str(uuid.uuid4())
        metadata = get_file_metadata(file_path)
        
        tasks[task_id] = {
            "task_id": task_id,
            "batch_id": batch_id,
            "status": "pending",
            "progress": 0,
            "current_step": "Queued",
            "file_path": file_path,
            "result_files": [],
            "metadata": metadata
        }
        
        batch_tasks["files"].append({
            "task_id": task_id,
            "file": file_path,
            "status": "pending"
        })
        
        # Add to background tasks
        background_tasks.add_task(run_separation, task_id, file_path, duration)
    
    return {"batch_id": batch_id, "total_files": len(media_files), "files": batch_tasks["files"]}

@app.post("/api/folder/scan")
async def scan_folder(payload: dict):
    """Scan a folder and return list of media files (queue system)."""
    folder_path = payload.get("folder_path")
    
    print(f"\n{Fore.CYAN}=== Folder Scan Request ==={Style.RESET_ALL}")
    print(f"Folder path: {folder_path}")
    
    if not folder_path or not os.path.isdir(folder_path):
        print(f"{Fore.RED}Folder not found: {folder_path}{Style.RESET_ALL}")
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Supported extensions
    video_extensions = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.wmv')
    audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma')
    supported_extensions = video_extensions + audio_extensions
    
    # Find all media files with metadata
    media_files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(supported_extensions):
            file_path = os.path.join(folder_path, f)
            try:
                metadata = get_file_metadata(file_path)
                media_files.append({
                    "id": str(uuid.uuid4()),
                    "file_path": file_path,
                    "filename": f,
                    "metadata": metadata,
                    "selected": True  # All files selected by default
                })
                print(f"  Found: {f} ({metadata.get('duration', 'N/A')})")
            except Exception as e:
                print(f"{Fore.YELLOW}Error getting metadata for {f}: {e}{Style.RESET_ALL}")
                # Still add file even if metadata fails
                media_files.append({
                    "id": str(uuid.uuid4()),
                    "file_path": file_path,
                    "filename": f,
                    "metadata": {"duration": "N/A", "resolution": "N/A"},
                    "selected": True
                })
    
    print(f"Total files found: {len(media_files)}")
    
    if not media_files:
        print(f"{Fore.RED}No media files found in folder{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="No media files found in folder")
    
    # Create queue session
    queue_id = str(uuid.uuid4())
    tasks[queue_id] = {
        "queue": True,
        "folder": folder_path,
        "files": media_files,
        "created_at": asyncio.get_event_loop().time()
    }
    
    print(f"Queue ID: {queue_id}")
    print(f"{Fore.GREEN}✓ Folder scan complete{Style.RESET_ALL}\n")
    
    return {
        "queue_id": queue_id,
        "folder": folder_path,
        "files": media_files,
        "total_files": len(media_files)
    }

@app.post("/api/folder-queue/update")
async def update_folder_queue(payload: dict):
    """Update the queue (remove files, toggle selection)."""
    queue_id = payload.get("queue_id")
    files = payload.get("files")  # Array of {id, selected}
    
    if not queue_id or queue_id not in tasks:
        raise HTTPException(status_code=404, detail="Queue not found")
    
    queue_data = tasks[queue_id]
    if not queue_data.get("queue"):
        raise HTTPException(status_code=400, detail="Not a queue task")
    
    # Update file selection
    for file_item in queue_data["files"]:
        for update_item in files:
            if file_item["id"] == update_item["id"]:
                file_item["selected"] = update_item["selected"]
    
    return {"status": "ok", "files": queue_data["files"]}

@app.post("/api/folder-queue/remove")
async def remove_from_folder_queue(payload: dict):
    """Remove a specific file from the queue."""
    queue_id = payload.get("queue_id")
    file_id = payload.get("file_id")
    
    if not queue_id or queue_id not in tasks:
        raise HTTPException(status_code=404, detail="Queue not found")
    
    queue_data = tasks[queue_id]
    if not queue_data.get("queue"):
        raise HTTPException(status_code=400, detail="Not a queue task")
    
    # Remove file from queue
    queue_data["files"] = [f for f in queue_data["files"] if f["id"] != file_id]
    
    return {"status": "ok", "files": queue_data["files"], "total_files": len(queue_data["files"])}

@app.post("/api/folder-queue/process")
async def process_folder_queue(background_tasks: BackgroundTasks, payload: dict):
    """Start processing the selected files in the queue."""
    queue_id = payload.get("queue_id")
    model = payload.get("model", "both")
    duration = payload.get("duration")
    
    print(f"\n{Fore.CYAN}=== Batch Processing Request ==={Style.RESET_ALL}")
    print(f"Queue ID: {queue_id}")
    print(f"Model: {model}")
    
    if not queue_id or queue_id not in tasks:
        print(f"{Fore.RED}Queue not found: {queue_id}{Style.RESET_ALL}")
        raise HTTPException(status_code=404, detail="Queue not found")
    
    queue_data = tasks[queue_id]
    if not queue_data.get("queue"):
        print(f"{Fore.RED}Not a queue task{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="Not a queue task")
    
    # Filter selected files only
    selected_files = [f for f in queue_data["files"] if f.get("selected", True)]
    
    print(f"Total files in queue: {len(queue_data['files'])}")
    print(f"Selected files: {len(selected_files)}")
    
    if not selected_files:
        print(f"{Fore.RED}No files selected{Style.RESET_ALL}")
        raise HTTPException(status_code=400, detail="No files selected for processing")
    
    # Create batch task
    batch_id = str(uuid.uuid4())
    batch_tasks = {
        "batch_id": batch_id,
        "folder": queue_data["folder"],
        "queue_id": queue_id,
        "total_files": len(selected_files),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "files": []
    }
    
    print(f"Batch ID: {batch_id}")
    
    # Store batch info
    tasks[batch_id] = {
        "batch": True,
        **batch_tasks
    }
    
    # Process each selected file
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
        
        batch_tasks["files"].append({
            "task_id": task_id,
            "file": file_path,
            "filename": file_item["filename"],
            "status": "pending"
        })
        
        # Add to background tasks
        background_tasks.add_task(run_separation, task_id, file_path, duration)
    
    print(f"{Fore.GREEN}✓ Batch processing started with {len(selected_files)} files{Style.RESET_ALL}\n")
    
    # Clean up queue
    del tasks[queue_id]
    
    return {"batch_id": batch_id, "total_files": len(selected_files), "files": batch_tasks["files"]}

@app.get("/api/folder-queue/{queue_id}")
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

@app.get("/api/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get status of a batch folder processing."""
    if batch_id not in tasks:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch = tasks[batch_id]
    if not batch.get("batch"):
        raise HTTPException(status_code=400, detail="Not a batch task")
    
    # Update counts
    processed = 0
    success = 0
    failed = 0
    
    for file_info in batch.get("files", []):
        task_id = file_info.get("task_id")
        if task_id in tasks:
            task = tasks[task_id]
            file_info["status"] = task.get("status", "pending")
            file_info["progress"] = task.get("progress", 0)
            file_info["current_step"] = task.get("current_step", "")
            
            if task.get("status") in ["completed", "failed"]:
                processed += 1
                if task.get("status") == "completed":
                    success += 1
                else:
                    failed += 1
    
    batch["processed"] = processed
    batch["success"] = success
    batch["failed"] = failed
    
    return batch

@app.get("/api/library")
async def get_library():
    """Returns a list of all completed tasks from the JSON file."""
    return get_full_library()

@app.get("/api/presets")
async def get_presets():
    """Get available quality presets."""
    config = load_config()
    presets_file = "video.json"
    
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
    
    # Default presets
    return {
        "presets": {
            "fast": {"label": "Fast (Small Size)"},
            "balanced": {"label": "Balanced (Recommended)"},
            "quality": {"label": "High Quality (Large Size)"}
        },
        "current_preset": "balanced"
    }

@app.post("/api/presets")
async def set_preset(payload: dict):
    """Set the current quality preset."""
    preset_name = payload.get("preset")
    presets_file = "video.json"
    
    if not preset_name:
        raise HTTPException(status_code=400, detail="Preset name required")
    
    if os.path.exists(presets_file):
        try:
            with open(presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            presets = data.get("presets", {})
            if preset_name not in presets:
                raise HTTPException(status_code=404, detail="Preset not found")
            
            # Apply preset settings
            data["current_preset"] = preset_name
            if "video" in presets[preset_name]:
                data["video"] = presets[preset_name]["video"]
            if "audio" in presets[preset_name]:
                data["audio"] = presets[preset_name]["audio"]
            if "output" in presets[preset_name]:
                data["output"] = presets[preset_name]["output"]
            
            with open(presets_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            
            return {"status": "ok", "preset": preset_name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="video.json not found")

@app.post("/api/open-folder")
async def open_folder(payload: dict):
    """Opens the directory of a file in Windows Explorer."""
    path = payload.get("path")
    if not path or not os.path.exists(path):
        # Even if file is gone, try to open the parent directory
        if path:
            parent = os.path.dirname(path)
            if os.path.exists(parent):
                os.startfile(parent)
                return {"status": "opened_parent"}
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Open folder and select the file (non-blocking)
    try:
        norm_path = os.path.normpath(path)
        # Use Popen to not block the server, and shell=True for explorer
        subprocess.Popen(f'explorer /select,"{norm_path}"', shell=True)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error opening explorer: {e}")
        # Fallback to opening directory
        os.startfile(os.path.dirname(norm_path))
        return {"status": "opened_parent_fallback"}

@app.post("/api/open-file")
async def open_file(payload: dict):
    """Opens a file directly with the default system application 🎬."""
    path = payload.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fajl nije pronađen")
    
    try:
        os.startfile(os.path.normpath(path))
        return {"status": "ok"}
    except Exception as e:
        print(f"Error opening file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/deno-info")
async def get_deno_info():
    """Returns information from Deno runtime 🦖."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deno_hello.ts")
    return run_deno_script(script_path)

@app.post("/api/delete-file")
async def delete_file(payload: dict):
    """Deletes the result file from disk and removes it from the library 🗑️."""
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="Task ID is required")
    
    try:
        library = get_full_library()
        new_library = []
        file_to_delete = None
        
        for item in library:
            if item.get("task_id") == task_id:
                res_files = item.get("result_files", [])
                if res_files:
                    file_to_delete = res_files[0]
            else:
                new_library.append(item)
        
        # Delete from disk if found
        if file_to_delete and os.path.exists(file_to_delete):
            try:
                os.remove(file_to_delete)
                print(f"Deleted file: {file_to_delete}")
            except Exception as e:
                print(f"Error deleting file from disk: {e}")
        
        # Save updated library
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(new_library, f, indent=4)
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Error in delete_file endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    # Load queue and notifications on startup
    load_queue()
    load_notifications()
    
    print(f"\n{Fore.CYAN}=== Application Starting ==={Style.RESET_ALL}")
    print(f"Loaded {len(download_queue)} queued downloads")
    print(f"Loaded {len(notifications)} notifications")
    
    # Show queue resumption status
    if download_queue:
        pending_count = sum(1 for q in download_queue if q.get('status') == 'pending')
        if pending_count > 0:
            print(f"{Fore.GREEN}✓ Resuming {pending_count} pending download(s)...{Style.RESET_ALL}")
            # Auto-start queue processing
            asyncio.create_task(process_queue())
    
    # Clean up old temporary files
    cleanup_temp_files()
    
    print(f"{Fore.GREEN}✓ Backend ready on http://0.0.0.0:8000{Style.RESET_ALL}\n")

    # Set log_level to "warning" to hide INFO spam
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
