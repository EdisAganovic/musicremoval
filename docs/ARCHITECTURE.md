# Architecture Overview

## Quick Reference

### Backend (Python) - Modular Structure

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `main.py` | CLI entry point for vocal separation | `download`, `separate` commands |
| `backend/__main__.py` | FastAPI server entry point | `uvicorn.run()` |
| `backend/backend.py` | FastAPI app, mounts all routers | `startup_event()`, `shutdown_event()` |
| `backend/models.py` | Pydantic schemas for API requests/responses | `DownloadRequest`, `TaskStatus`, `QueueItem` |
| `backend/config.py` | Shared state, config, utility functions | `tasks`, `download_queue`, `save_to_library()`, `log_console()` |
| **backend/routes/** | API endpoint handlers | |
| `routes/downloads.py` | YouTube download & queue endpoints | `get_yt_formats()`, `download_video()`, `add_to_queue()` |
| `routes/separation.py` | Vocal separation endpoints | `separate_audio()`, `scan_folder()`, `process_folder_queue()` |
| `routes/library.py` | Library management endpoints | `get_library()`, `delete_file()`, `open_folder()` |
| `routes/notifications.py` | Notifications & system info | `get_notifications()`, `get_system_info()` |
| **backend/services/** | Business logic layer | |
| `services/download_service.py` | YouTube download logic (yt-dlp) | `run_yt_dlp()` |
| `services/queue_service.py` | Queue processing logic | `process_queue()` |
| **backend/modules/** | Core processing modules | |
| `modules/module_processor.py` | Main orchestrator for vocal separation | `process_file()` |
| `modules/module_demucs.py` | Demucs AI model wrapper | `separate_with_demucs()` |
| `modules/module_spleeter.py` | Spleeter AI model wrapper | `separate_with_spleeter()` |
| `modules/module_ffmpeg.py` | FFmpeg wrapper for audio/video processing | `get_file_metadata()`, `download_ffmpeg()` |
| `modules/module_ytdlp.py` | YouTube video downloader | `download_video()` |
| `modules/module_audio.py` | Audio alignment and mixing | `align_audio_tracks()`, `mix_audio_tracks()` |
| `modules/module_cuda.py` | GPU detection and validation | `check_gpu_cuda_support()` |
| `modules/module_deno.py` | Deno runtime bridge | Execute TS/JS from Python |
| `modules/module_file.py` | File utilities | File operations and helpers |
| `modules/module_tools.py` | CLI utility for audio track inspection | `list_tracks` command |

### Frontend (React)

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| `App.jsx` | Root component with tab navigation | Tab switching, layout, status footer, console panel, settings modal |
| `SeparationTab.jsx` | File upload & vocal separation UI | Drag-drop, batch processing, progress polling |
| `DownloaderTab.jsx` | YouTube downloader | Format selection, queue system, subtitles, playlist support |
| `LibraryTab.jsx` | Processed files browser | Search, sort, bulk delete, re-separate, folder filter |
| `NotificationBell.jsx` | Notification dropdown | Unread count, mark read, clear all |
| `NotificationContext.jsx` | Notification state management | Auto-polling, optimistic updates |
| `api/index.js` | Centralized API client | Axios instance, organized endpoints, 30s timeout |

## Backend Structure

```
backend/
├── backend.py            # FastAPI app, mounts routers (~145 lines)
├── __main__.py           # Entry point for python -m backend
├── models.py             # Pydantic schemas
├── config.py             # Shared state, utilities, cleanup scheduler (~950 lines)
├── routes/
│   ├── __init__.py
│   ├── downloads.py        # /api/download, /api/queue/*, /api/yt-formats (~355 lines)
│   ├── separation.py       # /api/separate*, /api/folder/*, /api/batch-status/* (~496 lines)
│   ├── library.py          # /api/library, /api/delete-file, /api/open-* (~283 lines)
│   └── notifications.py    # /api/notifications, /api/system-info (~270 lines)
├── services/
│   ├── __init__.py
│   ├── download_service.py # yt-dlp integration (~236 lines)
│   └── queue_service.py    # Download queue processor (~61 lines)
└── modules/
    ├── __init__.py
    ├── module_processor.py   # Main orchestrator (calls all other modules)
    ├── module_ffmpeg.py      # FFmpeg wrapper (metadata, conversion, normalization)
    ├── module_ytdlp.py       # YouTube downloader (yt-dlp integration)
    ├── module_spleeter.py    # Spleeter AI separation
    ├── module_demucs.py      # Demucs AI separation
    ├── module_audio.py       # Audio alignment, mixing, sync correction
    ├── module_cuda.py        # GPU/CUDA detection
    ├── module_deno.py        # Deno runtime bridge
    ├── module_file.py        # File utilities
    └── module_tools.py       # CLI utility for inspecting audio tracks
```

## Data Flow

### Vocal Separation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                      │
│    CLI: main.py separate --file OR web UI upload                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  routes/separation.py OR module_processor.process_file()                │
│    1. Validate input file                                               │
│    2. Check GPU (module_cuda)                                           │
│    3. Get audio tracks (module_ffmpeg)                                  │
│    4. Extract audio to WAV                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────────┐       ┌───────────────────────┐
        │  module_spleeter      │       │  module_demucs        │
        │  - Split >10min       │       │  - Split >10min       │
        │  - 2stems model       │       │  - htdemucs model     │
        │  - Parallel workers   │       │  - Parallel workers   │
        └───────────────────────┘       └───────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  module_audio.align_audio_tracks()                                      │
│    - Cross-correlation to detect lag                                    │
│    - Pad earlier track to sync                                          │
│    - Mix both tracks (0.5 + 0.5)                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  module_ffmpeg.convert_audio_with_ffmpeg()                              │
│    - Apply loudnorm normalization                                       │
│    - Convert to output format (AAC/MP3/FLAC)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: ./nomusic/ folder + update library.json                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### YouTube Download Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                      │
│    Web UI: Paste URL → Analyze → Select Format → Download              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  routes/downloads.py                                                    │
│    POST /api/yt-formats  → Get available formats                        │
│    POST /api/download    → Start download task                          │
│    Detects: Single video, Playlist, Channel, Mix                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  services/download_service.run_yt_dlp()                                 │
│    1. Initialize task in tasks dict                                     │
│    2. Configure yt-dlp options (format, subtitles)                      │
│    3. Download video/audio with progress hooks                          │
│    4. Post-process (audio extraction if needed)                         │
│    5. Save to library.json                                              │
│    6. Auto-separate if requested                                        │
│    7. Retry logic (3 attempts, exponential backoff)                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: ./download/ folder + library.json update                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Playlist/Channel Download Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. POST /api/yt-formats with playlist/channel URL                      │
│  2. Backend detects playlist via regex patterns                         │
│  3. Returns: {is_playlist: true, videos: [{id, title, thumbnail, ...}]} │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend: Display video grid with thumbnails                           │
│  - Select/deselect individual videos                                    │
│  - Select All / Deselect All                                            │
│  - Show video ID, duration, title                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  POST /api/queue/add-batch with selected video IDs                      │
│  - Adds all selected videos to download_queue.json                      │
│  - Returns: {added: X, status: "queued"}                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Queue processing (manual or auto)                                      │
│  - Processes each video sequentially                                    │
│  - Updates queue state after each completion                            │
│  - Supports auto-separate toggle per video                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Dependencies

```
backend.py (FastAPI)
  └── routes/
        ├── downloads.py
        │     ├── services/download_service.py (run_yt_dlp)
        │     ├── services/queue_service.py (process_queue)
        │     └── config.py (tasks, download_queue, save_to_library)
        ├── separation.py
        │     ├── backend/modules/module_processor.py (process_file)
        │     ├── backend/modules/module_ffmpeg.py (get_file_metadata)
        │     └── config.py (tasks, add_notification)
        ├── library.py
        │     ├── backend/modules/module_ffmpeg.py (get_file_metadata_cached)
        │     └── config.py (get_full_library, save_to_library)
        └── notifications.py
              └── config.py (console_logs, notifications, get_full_library)

backend/modules/module_processor.py
  ├── backend/modules/module_cuda (check_gpu_cuda_support)
  ├── backend/modules/module_ffmpeg (get_audio_duration, convert_audio_with_ffmpeg)
  ├── backend/modules/module_spleeter (separate_with_spleeter)
  ├── backend/modules/module_demucs (separate_with_demucs)
  └── backend/modules/module_audio (align_audio_tracks, mix_audio_tracks)

main.py (CLI)
  ├── backend/modules/module_ffmpeg (download_ffmpeg)
  ├── backend/modules/module_ytdlp (download_video)
  └── backend/modules/module_processor (process_file)
```

## API Endpoints

### Download & Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/yt-formats` | Get available formats for YouTube URL (auto-detects playlist/channel) |
| POST | `/api/download` | Start YouTube download |
| POST | `/api/download/cancel` | Cancel active download |
| GET | `/api/status/{task_id}` | Get task progress |
| GET | `/api/downloads` | Get all active downloads |
| POST | `/api/queue/add` | Add single video to queue |
| POST | `/api/queue/add-batch` | Add multiple videos (playlist/channel) |
| GET | `/api/queue` | Get queue status |
| POST | `/api/queue/remove` | Remove from queue |
| POST | `/api/queue/clear` | Clear entire queue |
| POST | `/api/queue/start` | Start queue processing |
| POST | `/api/queue/stop` | Stop queue processing |

### Separation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/separate` | Upload and separate audio file |
| POST | `/api/separate-file` | Separate existing file from library |
| POST | `/api/folder/scan` | Scan folder for media files |
| POST | `/api/folder-queue/remove` | Remove file from folder queue |
| POST | `/api/folder-queue/process` | Process selected files from folder |
| GET | `/api/folder-queue/{queue_id}` | Get folder queue status |
| GET | `/api/batch-status/{batch_id}` | Get batch processing status |

### Library

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/library` | Get all processed files |
| POST | `/api/delete-file` | Delete file from library |
| POST | `/api/open-file` | Open file with default app |
| POST | `/api/open-folder` | Open folder in explorer |
| GET | `/api/presets` | Get quality presets |
| POST | `/api/presets` | Set current preset |

### Notifications & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications` | Get all notifications |
| POST | `/api/notifications/test` | Send test notification |
| POST | `/api/notifications/mark-read` | Mark all as read |
| POST | `/api/notifications/mark-single-read` | Mark single as read |
| POST | `/api/notifications/clear` | Clear all notifications |
| GET | `/api/console-logs` | Get recent console logs |
| POST | `/api/console-logs/clear` | Clear console logs |
| GET | `/api/system-info` | Get system info (GPU, packages, storage) |
| GET | `/api/deno-info` | Get Deno runtime info |

## Key JSON Files

| File | Purpose | Updated By |
|------|---------|------------|
| `library.json` | Processed files metadata | Backend (save_to_library) |
| `download_queue.json` | YouTube download queue state | Backend (save_queue) |
| `notifications.json` | User notification history | Backend (save_notifications) |
| `metadata_cache.json` | File metadata cache | Backend (save_metadata_cache) |
| `tasks.json` | Active task persistence | Backend (save_tasks_async) |
| `video.json` | Quality presets + configuration | Frontend/Backend |

## Configuration (video.json)

```json
{
  "presets": {
    "fast": { 
      "video": { "codec": "copy", "bitrate": "0" },
      "audio": { "codec": "aac", "bitrate": "128k" },
      "output": { "format": "mp4" }
    },
    "balanced": { 
      "video": { "codec": "h264_nvenc", "bitrate": "2500k" },
      "audio": { "codec": "aac", "bitrate": "192k" },
      "output": { "format": "mp4" }
    },
    "quality": { 
      "video": { "codec": "hevc_nvenc", "bitrate": "8000k" },
      "audio": { "codec": "aac", "bitrate": "256k" },
      "output": { "format": "mp4" }
    }
  },
  "video": { "codec": "...", "bitrate": "..." },
  "audio": { "codec": "...", "bitrate": "..." },
  "output": { "format": "mp4" },
  "processing": { "demucs_workers": 2 }
}
```

## Environment Configuration

### API Base URL (.env)

```
VITE_API_BASE_URL=http://localhost:5170/api
```

- Centralized port configuration
- Read by `frontend/src/api/index.js`
- No hardcoded URLs in components

## Temporary Files

| Path | Purpose | Cleaned |
|------|---------|---------|
| `_temp/` | General temp files | On startup (>24h) + on success |
| `uploads/` | Uploaded files for separation | After processing |
| `spleeter_out/` | Spleeter intermediate output | On startup (>24h) |
| `demucs_out/` | Demucs intermediate output | On startup (>24h) |
| `_processing_intermediates/` | Batch processing temp | On startup (>24h) |
| `download/` | YouTube downloads | Manual (user data) |
| `nomusic/` | Final output | Never (user data) |

## Processing Pipeline Steps

1. **Input Validation** - Check file exists, get audio tracks
2. **GPU Check** - Detect CUDA availability (module_cuda)
3. **Audio Extraction** - Extract to WAV with FFmpeg (stereo downmix)
4. **AI Separation** - Run Spleeter and Demucs (parallel if >10min)
5. **Alignment** - Cross-correlation to fix millisecond offsets
6. **Mixing** - Combine both model outputs (equal weight)
7. **Sync Correction** - Detect and pad any remaining lag
8. **Normalization** - Apply loudnorm (EBU R128)
9. **Final Encode** - Convert to output format with video (if applicable)
10. **Cleanup** - Remove temp files (unless --temp flag)

## Error Handling Strategy

- **Model Failure**: If Spleeter OR Demucs fails, continue with the other
- **Alignment Failure**: Fall back to unaligned mix
- **FFmpeg Failure**: Return False, abort processing
- **GPU Unavailable**: Fall back to CPU (slower but functional)
- **404 on Polling**: Treat as task completion (backend cleaned up)
- **Download Failure**: Retry with exponential backoff (2s, 4s, 8s), max 3 attempts
- **Duplicate Detection**: Warn user if file already exists in library

## Performance Notes

- **Segmentation**: Files >10min split into 600s chunks
- **Parallel Workers**: Demucs uses `demucs_workers` from config (default: 2)
- **Memory**: Demucs uses ~8GB RAM per concurrent worker
- **GPU**: 5-10x faster than CPU for AI models
- **Metadata Cache**: Fast library scanning with cached file metadata
- **Non-blocking Downloads**: yt-dlp runs in thread pool executor
- **Hot Reload**: Uvicorn excludes temp directories to prevent crashes

## Quality Presets

| Preset | Video Codec | Video Bitrate | Audio Codec | Audio Bitrate | Use Case |
|--------|-------------|---------------|-------------|---------------|----------|
| **Fast** | copy | 0 | AAC | 128k | Quick downloads, small size |
| **Balanced** | h264_nvenc | 2500k | AAC | 192k | Default, good quality/size |
| **Quality** | hevc_nvenc | 8000k | AAC | 256k | Best quality, larger files |

---

## Frontend Architecture

### Component Hierarchy

```
App.jsx (Root)
├── NotificationProvider (Context)
│   └── NotificationBell (Header)
├── Header (Logo, Title)
├── Tab Navigation (Pill-style)
│   ├── Separation Tab
│   ├── Downloader Tab
│   └── Library Tab
└── Footer (Status indicators)
```

### State Management

| State | Location | Purpose |
|-------|----------|---------|
| `activeTab` | App.jsx | Current tab selection |
| `notifications` | NotificationContext | Global notification state |
| `file`, `status`, `progress` | SeparationTab | Upload/processing state |
| `url`, `queue`, `videoInfo` | DownloaderTab | Download state |
| `items`, `selectedItems`, `folderFilter` | LibraryTab | Library items + selection + filter |
| `lastVideoId`, `lastSelectedFormat` | localStorage | Remember format preference per video |

### API Client Layer

```javascript
// frontend/src/api/index.js
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5170/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export const libraryAPI = { /* ... */ };
export const separationAPI = { /* ... */ };
export const downloadAPI = { /* ... */ };
export const queueAPI = { /* ... */ };
export const notificationsAPI = { /* ... */ };
```

### Polling Intervals

| Feature | Interval | Purpose |
|---------|----------|---------|
| Task progress | 1000ms | Real-time separation progress |
| Batch progress | 2000ms | Batch processing updates |
| Queue status | 2000ms | Download queue updates |
| Notifications | 3000ms | New notification checks |
| Library refresh | 10000ms | Auto-refresh completed files |

### Design System

- **Framework**: React 19 + Vite 7
- **Animations**: framer-motion (layout transitions, hover effects)
- **Icons**: lucide-react
- **Styling**: Tailwind CSS with custom glassmorphism
- **Colors**: Dark theme with primary (blue/purple) and accent (emerald) gradients
- **Effects**: Backdrop blur, gradient borders, shadow layers
- **Notifications**: react-hot-toast for toast messages

### Key UI Features

**Separation Tab:**
- Drag & drop with visual feedback
- Mode switch (Single File / Process Folder)
- File selection checkboxes for batch
- Progress bar with current step
- Result cards with action buttons

**Downloader Tab:**
- URL analysis with thumbnail preview
- Playlist/channel detection with video grid
- Select/deselect individual videos
- Format filtering (audio/video) with file size preview
- Subtitle language selection
- Queue panel with management controls
- Download cancellation
- Remember format preference per video
- Auto-separate toggle

**Library Tab:**
- Search and sort controls
- Folder filter (All Files / Download / NoMusic)
- Quick actions: Open Download, Open NoMusic
- Multi-select with bulk operations
- File metadata display
- Smart separate button (hides for processed files)
- Quick actions: play, separate, open folder, delete

### API Communication Pattern

```javascript
// 1. Trigger action
const handleUpload = async () => {
  // 2. Start processing state
  setStatus("processing");

  // 3. Call API
  const response = await separationAPI.upload(formData);
  setTaskId(response.data.task_id);

  // 4. Poll for progress (useEffect)
  useEffect(() => {
    const interval = setInterval(async () => {
      const status = await separationAPI.getStatus(taskId);
      setProgress(status.data.progress);
      if (status.data.status === "completed") {
        clearInterval(interval);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [taskId]);
};
```

---

## Recent Changes (2026-03-02)

### Version 0.0.6 - Task Persistence & Background Cleanup

#### Task State Persistence
- **Tasks saved to disk**: Active tasks persisted to `tasks.json` for recovery after restart
- **Async task management**: Thread-safe task operations with locks (`tasks_lock`)
- **Auto-cleanup**: Completed/failed tasks older than 24 hours removed automatically

#### Background Cleanup Scheduler
- **Periodic cleanup**: Runs every hour to clean temp files and stale data
- **Configurable interval**: `start_cleanup_scheduler(interval_seconds)`
- **Graceful shutdown**: Cleanup task cancelled properly on backend shutdown

#### Safety Improvements
- **Safe file operations**: `safe_remove()`, `safe_makedirs()`, `safe_file_copy()`, `safe_file_move()`
- **Path validation**: `safe_path()` prevents path traversal attacks
- **URL validation**: `validate_url()`, `validate_youtube_url()` for input sanitization
- **Filename sanitization**: `sanitize_filename()` removes invalid characters
- **Transaction context**: `TransactionContext` for rollback support

#### New CLI Tool
- **module_tools.py**: Standalone CLI for inspecting audio tracks in video files
  - Usage: `python -m backend.modules.module_tools list_tracks <file>`

#### Frontend Enhancements
- **Console Panel**: Real-time log viewer in UI (toggle with button)
- **Settings Modal**: System info display with GPU, CUDA, package versions
- **React Hot Toast**: Toast notifications for user feedback

### Version 0.0.3 - Playlist Support & Configuration Centralization

#### YouTube Downloader Enhancements
- **Playlist/Channel Download**: Full support for playlists, channels, and mixes
- **Video ID Display**: Shows YouTube video ID for easy identification
- **Remember Format Preference**: Saves selected format per video in localStorage
- **File Size Preview**: Shows estimated file size in format dropdown

#### Library Improvements
- **Folder Filter System**: Filter by source folder (All/Download/NoMusic)
- **Open Folder Quick Actions**: One-click access to download and nomusic folders
- **Smart Separate Button**: Hides for already-separated files

#### Configuration
- **Centralized Port Configuration**: Single `.env` file for API base URL
- **API Client Layer**: Centralized API communication in `frontend/src/api/index.js`

#### UI/UX
- **Compact Header**: Reduced size by ~50%
- **Smoother Tab Transitions**: 2x faster animations (0.15s)
- **Library Table Layout**: Replaced card layout with compact table

### Version 0.0.2 - Queue System & Batch Processing

#### Major Features
- **Download Queue System**: Full queue management with persistent storage
- **Folder Batch Processing**: Process entire folders with interactive UI
- **In-App Notification System**: Real-time notifications with bell component
- **Download Retry Logic**: Exponential backoff (3 attempts)
- **Auto Disk Cleanup**: Cleans temp files >24h on startup
- **Duplicate Detection**: Prevents downloading same content twice
- **Quality Presets System**: Fast/Balanced/Quality presets
- **Library Search & Bulk Operations**: Advanced library management

#### UI Additions
- Queue UI in Downloader with progress bars
- Folder Processing UI with file preview
- Notification Bell with unread counter
- Library table with multi-select

### Version 0.0.1 - Initial Release

- Core vocal separation with Demucs + Spleeter
- YouTube downloader with format selection
- Deno bridge implementation
- Library management with direct playback

---

## Environment & Dependencies

- **Python**: 3.10+ (UV managed)
- **Backend Version**: 0.0.6 (pyproject.toml)
- **Frontend Version**: 0.0.5 (package.json)
- **Node.js**: Vite/React frontend
- **Deno**: 2.5+ for runtime bridge
- **React**: 19.2.0
- **Vite**: 7.3.1
- **AI Models**: Demucs (htdemucs), Spleeter (2stems)
- **FFmpeg**: Auto-downloaded if missing
- **yt-dlp**: YouTube download with remote components

## Project Structure

```
demucspleeter/
├── main.py                 # CLI entry point
├── run_app.bat             # Windows startup script
├── pyproject.toml          # Python project config (version 0.0.6)
├── requirements.txt        # Python dependencies
├── deno.json               # Deno configuration
├── backend/                # FastAPI backend
│   ├── backend.py          # FastAPI app with startup/shutdown events
│   ├── __main__.py         # Entry point for python -m backend
│   ├── models.py           # Pydantic request/response schemas
│   ├── config.py           # Shared state, utilities, cleanup scheduler
│   ├── routes/             # API endpoint handlers
│   │   ├── downloads.py    # YouTube download & queue endpoints
│   │   ├── separation.py   # Vocal separation endpoints
│   │   ├── library.py      # Library management endpoints
│   │   └── notifications.py # Notifications & system info
│   ├── services/           # Business logic layer
│   │   ├── download_service.py  # yt-dlp download logic
│   │   └── queue_service.py     # Queue processing logic
│   └── modules/            # Core processing modules
│       ├── module_processor.py  # Main orchestrator
│       ├── module_ffmpeg.py     # FFmpeg wrapper
│       ├── module_ytdlp.py      # YouTube downloader
│       ├── module_spleeter.py   # Spleeter AI separation
│       ├── module_demucs.py     # Demucs AI separation
│       ├── module_audio.py      # Audio alignment/mixing
│       ├── module_cuda.py       # GPU detection
│       ├── module_deno.py       # Deno runtime bridge
│       ├── module_file.py       # File utilities
│       └── module_tools.py      # CLI utility for audio track inspection
├── frontend/               # React frontend (Vite)
│   ├── src/
│   │   ├── App.jsx         # Root component with tabs, console, settings
│   │   ├── main.jsx        # Entry point
│   │   ├── components/     # Tab components
│   │   │   ├── SeparationTab.jsx
│   │   │   ├── DownloaderTab.jsx
│   │   │   ├── LibraryTab.jsx
│   │   │   └── NotificationBell.jsx
│   │   ├── contexts/       # React contexts
│   │   │   └── NotificationContext.jsx
│   │   └── api/            # API client
│   │       └── index.js
│   ├── package.json        # NPM dependencies (v0.0.5)
│   └── vite.config.js      # Vite configuration
├── data/                   # Persistent data files
│   ├── library.json        # Processed files metadata
│   ├── download_queue.json # Queue state
│   ├── notifications.json  # Notification history
│   ├── tasks.json          # Active task persistence
│   ├── metadata_cache.json # File metadata cache
│   └── video.json          # Quality presets + config
├── download/               # YouTube downloads (user data)
├── nomusic/                # Separated output (user data)
├── uploads/                # Temporary upload folder
├── _temp/                  # General temp files
├── _processing_intermediates/  # Batch processing temp
└── docs/                   # Documentation
    └── ARCHITECTURE.md     # This file
```
