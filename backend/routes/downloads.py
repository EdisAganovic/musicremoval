"""
Download and Queue API Routes.
"""
import uuid
import asyncio
import urllib.parse
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List, Dict

from config import (
    tasks, active_downloads, download_queue,
    save_queue, load_queue, add_notification, log_console
)
import core.state as state
from services.download_service import run_yt_dlp
from services.queue_service import process_queue
from models import (
    DownloadRequest, DownloadCancelRequest, QueueAddRequest,
    QueueBatchRequest, QueueActionRequest
)
from utils.helpers import format_duration

def normalize_youtube_url(url: str) -> str:
    """Normalizes youtube.com and youtu.be URLs, removing tracking parameters."""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.netloc in ["youtu.be", "www.youtu.be"]:
            video_id = parsed.path.strip("/")
            new_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Preserve playlist parameter if it exists
            query = urllib.parse.parse_qs(parsed.query)
            params = []
            if "list" in query:
                params.append(f"list={query['list'][0]}")
            if "t" in query:
                params.append(f"t={query['t'][0]}")
            if params:
                new_url += "&" + "&".join(params)
            return new_url
    except Exception:
        pass
    
    # Strip tracking parameter `si` from any URL to avoid yt-dlp issues
    if "si=" in url:
        import re
        url = re.sub(r'([?&])si=[^&]*(&|$)', r'\1', url).rstrip('?&')
    return url

router = APIRouter(prefix="/api", tags=["downloads"])


@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """Get task status by ID."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = tasks[task_id]
    return result


@router.get("/downloads")
async def get_all_downloads():
    """Get all active and recent download tasks."""
    active_tasks = [
        task for task in tasks.values()
        if task.get("status") in ["processing", "downloading", "separating"]
        and task.get("type") == "download"
    ]
    active_tasks.sort(key=lambda t: (t.get("status") != "processing", -t.get("progress", 0)))
    return active_tasks


@router.post("/yt-formats")
async def get_yt_formats(payload: dict):
    """Fetches available formats for a YouTube URL."""
    import yt_dlp
    from yt_dlp.networking.impersonate import ImpersonateTarget
    
    url = normalize_youtube_url(payload.get("url"))
    check_playlist = payload.get("check_playlist", False)
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        is_playlist_url = any(indicator in url for indicator in [
            '/playlist?', 'list=PL', 'list=UU', 'list=RD', 'list=LL',
            '/channel/', '/@', '/c/'
        ])

        if check_playlist and is_playlist_url:
            # Handle playlist/channel URLs
            if '/@' in url or '/channel/' in url:
                if '/@' in url:
                    channel_handle = url.split('/@')[1].split('?')[0].split('/')[0]
                    url = f"https://www.youtube.com/@{channel_handle}/videos"
                elif '/channel/' in url:
                    channel_id = url.split('/channel/')[1].split('?')[0].split('/')[0]
                    url = f"https://www.youtube.com/channel/{channel_id}/videos"

            if '/featured' in url:
                url = url.replace('/featured', '/videos')
            if '/shorts' in url:
                url = url.replace('/shorts', '/videos')

            log_console(f"Fetching playlist/channel info: {url}", "info")
            
            ydl_opts = {
                'quiet': True,
                'ignoreerrors': True,
                'noplaylist': False,
                'extract_flat': 'in_playlist',
                'remote_components': ['ejs:github'],
            }

            def get_playlist_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await asyncio.to_thread(get_playlist_info)
            videos = []
            entries = info.get('entries', []) if info.get('_type') in ['playlist', 'multi_video'] else [info]

            # Convert generator/iterator to list if necessary
            entries = list(entries)

            for entry in entries:
                if entry:
                    title = entry.get('title', 'Unknown')
                    # Skip missing or explicitly private/deleted videos
                    if not title or title.lower() in ['[private video]', '[deleted video]', 'private video', 'deleted video']:
                        continue

                    videos.append({
                        "id": entry.get('id', ''),
                        "title": title,
                        "thumbnail": entry.get('thumbnail', '') or next(iter(t['url'] for t in entry.get('thumbnails', []) if 'url' in t), ''),
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

        # Single video
        def get_video_info(use_impersonate=True):
            opts = {
                'quiet': True,
                'noplaylist': True,
                'remote_components': ['ejs:github'],
            }
            if use_impersonate:
                opts['impersonate'] = ImpersonateTarget(client='chrome')
                
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            # Try first with impersonate (often gets better formats but can fail on challenge)
            info = await asyncio.to_thread(lambda: get_video_info(use_impersonate=True))
        except Exception as e:
            log_console(f"Impersonate failed ({e}), falling back to standard extraction", "warning")
            # Fallback without impersonate (guarantees at least m3u8 fallback strings)
            info = await asyncio.to_thread(lambda: get_video_info(use_impersonate=False))
            
        if info is None:
            raise Exception("Video is no longer available or age-restricted (yt-dlp returned no metadata).")
            
        formats = []
        for f in info.get('formats', []):
            # Get size, prefer exact filesize
            fs = f.get('filesize')
            fsa = f.get('filesize_approx')
            size_val = fs if fs is not None else fsa
            
            # Skip if truly no size info
            if size_val is None or size_val == 0:
                continue
                
            # Extra protection: skip 'm3u8' protocols which are often the duplicates without real sizes
            if f.get('protocol') == 'm3u8_native' or 'm3u8' in f.get('url', ''):
                continue
                
            format_info = {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "note": f.get("format_note"),
                "filesize": size_val,
                "url": f.get("url")
            }
            note = f.get('format_note')
            note_str = f" ({note})" if note else ""
            
            vcodec = f.get('vcodec') or 'none'
            acodec = f.get('acodec') or 'none'
            
            # Show short codec names (e.g., avc1.4D401E -> avc1)
            codecs = []
            if vcodec != 'none':
                codecs.append(vcodec.split('.')[0])
            if acodec != 'none':
                codecs.append(acodec.split('.')[0])
                
            codec_str = f" [{'/'.join(codecs)}]" if codecs else ""

            label = f"{f.get('ext')} - {f.get('resolution')}{codec_str}{note_str}"
            if vcodec == 'none':
                label = f"Audio: {f.get('ext')}{codec_str}{note_str}"
            format_info["label"] = label
            formats.append(format_info)

        available_subs = []
        if 'subtitles' in info:
            for lang in info['subtitles']:
                available_subs.append({"code": lang, "label": f"{lang} (Subtitle)"})
        if 'automatic_captions' in info:
            for lang in info['automatic_captions']:
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


@router.post("/download")
async def download_video(background_tasks: BackgroundTasks, payload: dict):
    """Start a YouTube download."""
    url = normalize_youtube_url(payload.get("url"))
    format_type = payload.get("format", "audio")
    format_id = payload.get("format_id")
    auto_separate = payload.get("auto_separate", False)
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Check for duplicates in library
    from config import get_full_library
    library = get_full_library()
    for item in library:
        item_url = item.get("url")
        if item_url and (item_url == url or item_url.strip('/') == url.strip('/')):
            res_files = item.get("result_files", [])
            if res_files and all(__import__('os').path.exists(f) for f in res_files):
                return {
                    "status": "duplicate",
                    "message": f"URL already in library: {__import__('os').path.basename(res_files[0])}",
                    "existing_file": res_files[0],
                    "task_id": item.get("task_id")
                }

    # Check current active tasks
    for tid, task in tasks.items():
        if task.get("url") == url and task.get("status") in ["processing", "downloading", "separating"]:
            return {
                "status": "processing",
                "message": "URL is already being processed",
                "task_id": tid
            }

    task_id = str(uuid.uuid4())
    
    import time
    # Initialize task immediately to prevent 404 on polling
    tasks[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "progress": 0,
        "current_step": "Initializing download",
        "result_files": [],
        "url": url,
        "type": "download",
        "created_at": time.time()
    }
    from services.persistence import save_tasks_sync
    save_tasks_sync()
    
    background_tasks.add_task(run_yt_dlp, task_id, url, format_type, format_id, None, auto_separate, payload.get("subfolder"))
    return {"task_id": task_id}


@router.post("/download/cancel")
async def cancel_download(payload: DownloadCancelRequest):
    """Cancel an active download."""
    if payload.task_id not in active_downloads:
        # Check if already finished or stuck
        if payload.task_id in tasks:
            task = tasks[payload.task_id]
            if task.get("status") in ["completed", "failed", "cancelled"]:
                return {"status": "already_finished"}
            else:
                # Force cancel a stuck task (e.g. after server restart)
                task["status"] = "cancelled"
                task["current_step"] = "Cancelled (stuck task)"
                from services.persistence import save_tasks_sync
                save_tasks_sync()
                return {"status": "cancelled"}
        raise HTTPException(status_code=404, detail="Task not found")

    active_downloads[payload.task_id]["cancel_flag"] = True

    # Try to cancel yt-dlp
    ydl = active_downloads[payload.task_id].get("ydl")
    if ydl and hasattr(ydl, '_downloader'):
        try:
            ydl._downloader._num_downloads = float('inf')
        except (AttributeError, TypeError):
            pass

    return {"status": "cancelled"}


# ============== Queue Routes ==============

@router.post("/queue/stop")
async def stop_queue():
    """Stop queue processing and remove all pending (unstarted) items."""
    # Set the flag so queue_service loop exits
    state.queue_processing = False

    # Remove pending items from the queue
    removed = 0
    items_to_keep = []
    for item in download_queue:
        if item.get("status") == "pending":
            removed += 1
        else:
            items_to_keep.append(item)
    download_queue[:] = items_to_keep  # Mutate in-place to keep reference
    if removed > 0:
        save_queue()
    return {"status": "stopped", "removed_items": removed}


@router.post("/queue/add")
async def add_to_queue(background_tasks: BackgroundTasks, payload: QueueAddRequest):
    """Add a download to the queue."""
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL is required")

    url = normalize_youtube_url(payload.url)

    from config import get_full_library
    library = get_full_library()
    for item in library:
        if item.get("url") == url:
            return {"status": "already_downloaded", "task_id": item.get("task_id")}

    queue_item = {
        "queue_id": str(uuid.uuid4()),
        "url": url,
        "title": payload.title or "",
        "format_type": payload.format,
        "format_id": payload.format_id,
        "auto_separate": payload.auto_separate,
        "subfolder": payload.subfolder,
        "status": "pending",
        "task_id": None,
        "added_at": asyncio.get_event_loop().time()
    }

    download_queue.append(queue_item)
    save_queue()

    asyncio.create_task(process_queue())

    return {"queue_id": queue_item["queue_id"], "status": "queued"}


@router.post("/queue/add-batch")
async def add_to_queue_batch(background_tasks: BackgroundTasks, payload: QueueBatchRequest):
    """Add multiple videos to the download queue."""
    if not payload.videos:
        raise HTTPException(status_code=400, detail="No videos provided")

    added_count = 0
    for video in payload.videos:
        url = normalize_youtube_url(video.get("url"))
        if url:
            queue_item = {
                "queue_id": str(uuid.uuid4()),
                "url": url,
                "format_type": payload.format,
                "format_id": payload.format_id,
                "auto_separate": payload.auto_separate,
                "subfolder": payload.subfolder,
                "status": "pending",
                "task_id": None,
                "added_at": asyncio.get_event_loop().time(),
                "title": video.get("title", "Unknown")
            }
            download_queue.append(queue_item)
            added_count += 1

    save_queue()
    asyncio.create_task(process_queue())

    return {"added": added_count, "status": "queued"}


@router.get("/queue")
async def get_queue():
    """Get current download queue."""
    return {"queue": download_queue, "processing": state.queue_processing}


@router.post("/queue/remove")
async def remove_from_queue(payload: QueueActionRequest):
    """Remove an item from the queue."""
    if not payload.queue_id:
        raise HTTPException(status_code=400, detail="queue_id required")

    # Mutate in-place to keep the same list reference for queue_service
    download_queue[:] = [item for item in download_queue if item.get("queue_id") != payload.queue_id]
    save_queue()
    return {"status": "removed", "queue": download_queue}


@router.post("/queue/clear")
async def clear_queue():
    """Clear completed and failed items from the queue ("Clear Done")."""
    # Only remove finished items, keep pending and downloading
    download_queue[:] = [
        item for item in download_queue
        if item.get("status") not in ("completed", "failed")
    ]
    save_queue()
    return {"status": "cleared"}


@router.post("/queue/start")
async def start_queue(background_tasks: BackgroundTasks):
    """Start processing the queue."""
    background_tasks.add_task(process_queue)
    return {"status": "started"}


# NOTE: /queue/stop is defined above (merged stop + clear pending into one route)
