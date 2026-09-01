"""
Download and Queue API Routes.
"""
import os
import time
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
from utils.validation import is_youtube_url

def normalize_youtube_url(url: str) -> str:
    """Normalizes youtube.com and youtu.be URLs, removing tracking/search parameters."""
    if not url:
        return url
    url = url.strip()

    # Handle truncated or mobile prefixes like "m/watch...", "/watch...", "watch?v=..."
    if url.startswith("m/watch") or url.startswith("/watch") or url.startswith("watch?"):
        query_part = url[url.find("?"):] if "?" in url else ("?" + url.split("/", 1)[-1])
        url = f"https://www.youtube.com/watch{query_part}"
    elif not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    import re
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        query = urllib.parse.parse_qs(parsed.query)

        if netloc in ["youtu.be", "www.youtu.be"]:
            video_id = parsed.path.strip("/")
            params = []
            if "list" in query:
                params.append(f"list={query['list'][0]}")
            if "t" in query:
                params.append(f"t={query['t'][0]}")
            new_url = f"https://www.youtube.com/watch?v={video_id}"
            if params:
                new_url += "&" + "&".join(params)
            return new_url
        elif any(d in netloc for d in ["youtube.com", "m.youtube.com", "music.youtube.com"]):
            if parsed.path.startswith("/shorts/"):
                video_id = parsed.path.replace("/shorts/", "").strip("/").split("/")[0]
                return f"https://www.youtube.com/watch?v={video_id}"
            elif parsed.path == "/watch" or parsed.path.startswith("/watch"):
                video_id = query.get("v", [""])[0]
                if video_id:
                    params = [f"v={video_id}"]
                    if "list" in query:
                        params.append(f"list={query['list'][0]}")
                    if "t" in query:
                        params.append(f"t={query['t'][0]}")
                    return f"https://www.youtube.com/watch?{'&'.join(params)}"
    except Exception:
        pass
    
    # Generic parameter strip for other tracking params
    for param in ["si", "pp", "feature", "fbclid", "igshid", "utm_source", "utm_medium", "utm_campaign"]:
        url = re.sub(rf'([?&]){param}=[^&]*(&|$)', r'\1', url)
    url = url.rstrip('?&')
    return url

router = APIRouter(prefix="/api", tags=["downloads"])


@router.get("/settings/random-delay")
async def get_random_delay_setting():
    """Get the current state of random delay setting."""
    import core.state as state
    return {"enabled": state.random_delay_enabled}


@router.post("/settings/random-delay")
async def update_random_delay_setting(payload: dict):
    """Update the random delay setting."""
    import core.state as state
    enabled = payload.get("enabled", True)
    state.random_delay_enabled = enabled
    return {"status": "success", "enabled": state.random_delay_enabled}


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
    """Fetches available formats for any URL supported by yt-dlp (YouTube, Facebook, etc)."""
    import yt_dlp

    url = normalize_youtube_url(payload.get("url"))
    check_playlist = payload.get("check_playlist", False)

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    yt_url = is_youtube_url(url)

    try:
        # ── YouTube playlist / channel handling ──────────────────────────────
        if yt_url and check_playlist:
            is_playlist_url = any(indicator in url for indicator in [
                '/playlist?', 'list=PL', 'list=UU', 'list=RD', 'list=LL',
                '/channel/', '/@', '/c/'
            ])

            if is_playlist_url:
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
                    'socket_timeout': 30,
                    'retries': 5,
                    'no_warnings': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                }
                import os
                cookies_path = os.path.join("data", "cookies.txt")
                if os.path.exists(cookies_path):
                    ydl_opts['cookiefile'] = cookies_path

                def get_playlist_info():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)

                try:
                    info = await asyncio.to_thread(get_playlist_info)
                    if info:
                        videos = []
                        entries = info.get('entries', []) if info.get('_type') in ['playlist', 'multi_video'] else [info]
                        entries = list(entries)

                        for entry in entries:
                            if entry:
                                title = entry.get('title', 'Unknown')
                                if not title or title.lower() in ['[private video]', '[deleted video]', 'private video', 'deleted video']:
                                    continue
                                
                                # Safe thumbnail resolution
                                thumb = entry.get('thumbnail', '')
                                if not thumb:
                                    thumbnails_list = entry.get('thumbnails') or []
                                    thumb = next((t.get('url', '') for t in thumbnails_list if isinstance(t, dict) and t.get('url')), '')

                                videos.append({
                                    "id": entry.get('id', ''),
                                    "title": title,
                                    "thumbnail": thumb,
                                    "duration": format_duration(entry.get('duration', 0)),
                                    "url": entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id', '')}")
                                })

                        if len(videos) > 0 and info.get('_type') in ['playlist', 'multi_video']:
                            return {
                                "is_playlist": True,
                                "title": info.get("title", "Playlist"),
                                "thumbnail": info.get("thumbnail", ""),
                                "video_count": len(videos),
                                "videos": videos
                            }
                except Exception as pl_err:
                    log_console(f"Playlist extraction failed or playlist nonexistent ({pl_err}), falling back to single video analysis.", "warning")

        # ── Single video / non-YouTube URL ───────────────────────────────────
        def get_video_info():
            from modules.module_ffmpeg import FFMPEG_EXE
            ffmpeg_dir = os.path.dirname(FFMPEG_EXE) if os.path.exists(FFMPEG_EXE) else None

            opts = {
                'quiet': True,
                'noplaylist': True,
                'socket_timeout': 30,
                'retries': 5,
                'no_warnings': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
            if ffmpeg_dir:
                opts['ffmpeg_location'] = ffmpeg_dir
            cookies_path = os.path.join("data", "cookies.txt")
            if os.path.exists(cookies_path):
                opts['cookiefile'] = cookies_path

            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(get_video_info)

        if info is None:
            raise Exception("Video is unavailable or yt-dlp could not fetch metadata.")

        formats = []
        for f in info.get('formats', []):
            fs = f.get('filesize')
            fsa = f.get('filesize_approx')
            size_val = fs if fs is not None else fsa

            # For non-YouTube platforms, include formats even without known size
            # (Facebook, Instagram, TikTok often don't report exact sizes)
            if not yt_url:
                # Include if it has a resolution or is audio-only
                if f.get('resolution') is None and f.get('vcodec') not in [None, 'none'] and f.get('acodec') in [None, 'none']:
                    continue  # Skip video-only with no resolution info
            else:
                # For YouTube: skip if truly no size info
                if size_val is None or size_val == 0:
                    continue
                # Extra protection: skip m3u8 protocols which are often duplicates
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

            codecs = []
            if vcodec != 'none':
                codecs.append(vcodec.split('.')[0])
            if acodec != 'none':
                codecs.append(acodec.split('.')[0])

            codec_str = f" [{'/'.join(codecs)}]" if codecs else ""

            resolution = f.get('resolution') or 'audio'
            label = f"{f.get('ext')} - {resolution}{codec_str}{note_str}"
            if vcodec == 'none':
                label = f"Audio: {f.get('ext')}{codec_str}{note_str}"
            if size_val:
                label += f" ({size_val / 1024 / 1024:.1f} MB)"
            format_info["label"] = label
            formats.append(format_info)

        # Deduplicate by format_id
        seen_ids = set()
        unique_formats = []
        for f in formats:
            fid = f.get("format_id")
            if fid not in seen_ids:
                seen_ids.add(fid)
                unique_formats.append(f)

        available_subs = []
        if 'subtitles' in info:
            for lang in info['subtitles']:
                available_subs.append({"code": lang, "label": f"{lang} (Subtitle)"})
        if 'automatic_captions' in info:
            for lang in info['automatic_captions']:
                if not any(s['code'] == lang for s in available_subs):
                    available_subs.append({"code": lang, "label": f"{lang} (Auto-generated)"})

        # Determine platform
        import urllib.parse as _up
        platform = _up.urlparse(url).netloc.lower().replace('www.', '').split('.')[0]

        return {
            "is_playlist": False,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "id": info.get("id"),
            "formats": unique_formats,
            "subtitles": available_subs,
            "platform": platform,
            "is_youtube": yt_url,
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

    # Check for duplicates in library for matching format type (audio vs video)
    from config import get_full_library
    library = get_full_library()
    for item in library:
        item_url = item.get("url")
        if item_url and (item_url == url or item_url.strip('/') == url.strip('/')):
            res_files = item.get("result_files", [])
            if res_files and all(os.path.exists(f) for f in res_files):
                is_video_file = any(f.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v')) for f in res_files)
                if (format_type == 'video' and is_video_file) or (format_type == 'audio' and not is_video_file):
                    return {
                        "status": "duplicate",
                        "message": f"URL already in library: {os.path.basename(res_files[0])}",
                        "existing_file": res_files[0],
                        "task_id": item.get("task_id")
                    }

    # Check current active tasks
    for tid, task in tasks.items():
        if task.get("url") == url and task.get("status") in ["processing", "downloading", "separating"]:
            # If same format is already processing
            t_format = task.get("format", "audio")
            if t_format == format_type:
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
        "added_at": time.time()
    }

    download_queue.append(queue_item)
    save_queue()

    # Reset stale queue_processing flag if nothing is actually downloading
    if state.queue_processing:
        actually_downloading = any(
            item.get("status") == "downloading"
            for item in download_queue
        )
        if not actually_downloading:
            print(f"[Queue] Resetting stale queue_processing flag in /queue/add")
            state.queue_processing = False

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
                "added_at": time.time(),
                "title": video.get("title", "Unknown")
            }
            download_queue.append(queue_item)
            added_count += 1

    save_queue()

    # Reset stale queue_processing flag if nothing is actually downloading
    if state.queue_processing:
        actually_downloading = any(
            item.get("status") == "downloading"
            for item in download_queue
        )
        if not actually_downloading:
            print(f"[Queue] Resetting stale queue_processing flag in add-batch")
            state.queue_processing = False

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
    # Reset stale queue_processing flag if nothing is actually downloading
    if state.queue_processing:
        actually_downloading = any(
            item.get("status") == "downloading"
            for item in download_queue
        )
        if not actually_downloading:
            print(f"[Queue] Resetting stale queue_processing flag (was True but nothing downloading)")
            state.queue_processing = False
    background_tasks.add_task(process_queue)
    return {"status": "started"}


# NOTE: /queue/stop is defined above (merged stop + clear pending into one route)
