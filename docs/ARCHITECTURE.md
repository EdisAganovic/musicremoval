# Architecture Overview

## Quick Reference

### Backend (Python) - Modular Structure

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `main.py` | CLI entry point for vocal separation | `download`, `separate` commands |
| `backend/__main__.py` | FastAPI server entry point | `uvicorn.run()` |
| `backend/backend.py` | FastAPI app, mounts all routers | `startup_event()`, `shutdown_event()` |
| `backend/models.py` | Pydantic schemas for API requests/responses | `DownloadRequest`, `TaskStatus`, `QueueItem` |
| `backend/config.py` | Legacy config, re-exports from core/ | Compatibility layer |
| **backend/core/** | Core state and constants | |
| `core/state.py` | Shared global state with locks | `tasks`, `download_queue`, `notifications`, `*_lock` |
| `core/constants.py` | Hardcoded paths and settings | `LIBRARY_FILE`, `MAX_LOGS`, `QUEUE_FILE` |
| **backend/routes/** | API endpoint handlers | |
| `routes/downloads.py` | YouTube download & queue endpoints | `get_yt_formats()`, `download_video()`, `add_to_queue()` |
| `routes/separation.py` | Vocal separation endpoints | `separate_audio()`, `scan_folder()`, `process_folder_queue()` |
| `routes/library.py` | Library management endpoints | `get_library()`, `delete_file()`, `open_folder()` |
| `routes/notifications.py` | Notifications & system info | `get_notifications()`, `get_system_info()` |
| **backend/services/** | Business logic layer | |
| `services/download_service.py` | YouTube download logic (yt-dlp) | `run_yt_dlp()` |
| `services/queue_service.py` | Queue processing logic | `process_queue()` |
| `services/separation_service.py` | Vocal separation orchestration | `run_separation()` |
| `services/persistence.py` | JSON data persistence layer | `save_library()`, `load_library()`, `save_tasks_async()` |
| `services/cleanup.py` | Background cleanup scheduler | `cleanup_temp_files()`, `start_cleanup_scheduler()` |
| **backend/utils/** | Utility functions | |
| `utils/file_ops.py` | Safe file system operations | `safe_remove()`, `safe_makedirs()`, `safe_file_copy()` |
| `utils/validation.py` | Input validation | `validate_url()`, `validate_youtube_url()`, `safe_path()` |
| `utils/helpers.py` | General helper functions | `sanitize_filename()`, `format_duration()` |
| `utils/async_tools.py` | Async utilities | Async helpers and wrappers |
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
├── config.py             # Re-exports from core/ for backward compatibility
├── core/                 # Core state and constants (NEW)
│   ├── __init__.py
│   ├── state.py          # Global state variables and asyncio locks
│   └── constants.py      # File paths and threshold settings
├── routes/
│   ├── __init__.py
│   ├── downloads.py        # /api/download, /api/queue/*, /api/yt-formats (~355 lines)
│   ├── separation.py       # /api/separate*, /api/folder/*, /api/batch-status/* (~496 lines)
│   ├── library.py          # /api/library, /api/delete-file, /api/open-* (~283 lines)
│   └── notifications.py    # /api/notifications, /api/system-info (~270 lines)
├── services/
│   ├── __init__.py
│   ├── download_service.py # yt-dlp integration (~236 lines)
│   ├── queue_service.py    # Download queue processor (~61 lines)
│   ├── separation_service.py # Vocal separation service (NEW)
│   ├── persistence.py      # JSON persistence layer (NEW)
│   └── cleanup.py          # Background cleanup scheduler (NEW)
├── utils/                # Utility functions (NEW)
│   ├── __init__.py
│   ├── file_ops.py         # Safe file operations
│   ├── validation.py       # Input validation
│   ├── helpers.py          # General helper functions
│   └── async_tools.py      # Async utilities
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
        │     ├── services/persistence.py (save_library, load_library)
        │     ├── core/state.py (tasks, download_queue, active_downloads)
        │     └── utils/validation.py (validate_youtube_url)
        ├── separation.py
        │     ├── services/separation_service.py (run_separation)
        │     ├── services/persistence.py (save_tasks_async)
        │     ├── backend/modules/module_processor.py (process_file)
        │     ├── backend/modules/module_ffmpeg.py (get_file_metadata)
        │     └── core/state.py (tasks)
        ├── library.py
        │     ├── services/persistence.py (get_full_library, save_to_library)
        │     ├── backend/modules/module_ffmpeg.py (get_file_metadata_cached)
        │     ├── utils/file_ops.py (safe_remove)
        │     └── core/state.py (metadata_cache)
        └── notifications.py
              ├── services/persistence.py (save_notifications)
              └── core/state.py (console_logs, notifications)

backend/modules/module_processor.py
  ├── backend/modules/module_cuda (check_gpu_cuda_support)
  ├── backend/modules/module_ffmpeg (get_audio_duration, convert_audio_with_ffmpeg)
  ├── backend/modules/module_spleeter (separate_with_spleeter)
  ├── backend/modules/module_demucs (separate_with_demucs)
  └── backend/modules/module_audio (align_audio_tracks, mix_audio_tracks)

services/separation_service.py
  ├── backend/modules/module_processor.py (process_file)
  ├── backend/modules/module_ffmpeg.py (download_ffmpeg)
  ├── services/persistence.py (save_tasks_sync)
  └── core/state.py (tasks)

services/download_service.py
  ├── backend/modules/module_ytdlp.py (download_video)
  ├── services/persistence.py (save_to_library, add_notification)
  ├── utils/file_ops.py (safe_makedirs)
  └── core/state.py (tasks, active_downloads)

services/persistence.py
  ├── core/state.py (all state variables and locks)
  ├── core/constants.py (file paths, limits)
  └── utils/file_ops.py (safe_makedirs)

services/cleanup.py
  ├── services/persistence.py (save_metadata_cache)
  ├── utils/file_ops.py (safe_remove)
  └── core/state.py (tasks, metadata_cache)

main.py (CLI)
  ├── backend/modules/module_ffmpeg (download_ffmpeg)
  ├── backend/modules/module_ytdlp (download_video)
  ├── backend/modules/module_processor (process_file)
  └── utils/validation.py (validate_url)
```

## Core Layer (backend/core/)

The `core/` directory contains the foundational layer of the application, separating state management and constants from business logic.

### state.py
Global state variables with asyncio.Lock objects for thread-safe access:

| Variable | Type | Purpose |
|----------|------|---------|
| `tasks` | Dict[str, dict] | Active task storage (task_id -> task data) |
| `download_queue` | List[dict] | YouTube download queue items |
| `notifications` | List[dict] | User notification history |
| `active_downloads` | Dict[str, dict] | Running downloads with cancel flags |
| `metadata_cache` | Dict[str, dict] | Cached file metadata |
| `console_logs` | List[dict] | Console logs for frontend display |
| `*_lock` | asyncio.Lock | Thread-safe locks for each state variable |

### constants.py
Centralized configuration constants:

| Constant | Value | Purpose |
|----------|-------|---------|
| `LIBRARY_FILE` | "data/library.json" | Processed files metadata |
| `QUEUE_FILE` | "data/download_queue.json" | Download queue persistence |
| `NOTIFICATIONS_FILE` | "data/notifications.json" | Notification history |
| `METADATA_CACHE_FILE` | "data/metadata_cache.json" | File metadata cache |
| `TASKS_FILE` | "data/tasks.json" | Active tasks persistence |
| `MAX_LOGS` | 500 | Maximum console logs to retain |
| `MAX_NOTIFICATIONS` | 50 | Maximum notifications to retain |

## Utility Layer (backend/utils/)

The `utils/` directory contains reusable utility functions used across the backend.

### file_ops.py
Safe file system operations with error handling:
- `safe_remove()` - Remove files with error handling
- `safe_makedirs()` - Create directories safely
- `safe_file_copy()` - Copy files with validation
- `safe_file_move()` - Move files atomically
- `TransactionContext` - Context manager for rollback support

### validation.py
Input validation and sanitization:
- `safe_path()` - Prevent path traversal attacks
- `validate_url()` - Basic URL validation
- `validate_youtube_url()` - YouTube-specific URL validation
- `sanitize_filename()` - Remove invalid filename characters

### helpers.py
General helper functions:
- `sanitize_filename()` - Clean filenames for filesystem
- `format_duration()` - Format seconds to human-readable duration
- `format_file_size()` - Format bytes to human-readable size

### async_tools.py
Async utility functions:
- Async helpers for concurrent operations
- Lock management utilities

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

## Services Layer (backend/services/)

The `services/` directory contains business logic layer, separating domain operations from API routing and data persistence.

### download_service.py
YouTube download orchestration using yt-dlp:
- `run_yt_dlp()` - Main download function with retry logic
- Handles format selection, subtitles, playlist extraction
- Progress callbacks for real-time updates
- Auto-separation integration after download

### queue_service.py
Download queue management:
- `process_queue()` - Sequential queue processor
- Handles queue state transitions
- Integration with download_service for each item

### separation_service.py
Vocal separation orchestration:
- `run_separation()` - Main separation workflow
- Manages task lifecycle (pending → processing → completed/failed)
- Calls module_processor for actual AI processing
- Handles batch progress updates

### persistence.py
JSON data persistence layer:
- Library operations: `save_library()`, `load_library()`, `get_full_library()`
- Task persistence: `save_tasks_async()`, `save_tasks_sync()`, `load_tasks()`
- Queue persistence: `save_queue()`, `load_queue()`
- Notification persistence: `save_notifications()`, `load_notifications()`
- Metadata cache: `save_metadata_cache()`, `load_metadata_cache()`
- Console logs: `log_console()`, `get_console_logs()`
- Initialization: `init_data_directory()`

### cleanup.py
Background maintenance and cleanup:
- `cleanup_temp_files()` - Remove temp files older than 24h
- `cleanup_metadata_cache()` - Remove stale cache entries
- `cleanup_old_tasks()` - Remove completed tasks older than 24h
- `start_cleanup_scheduler()` - Periodic cleanup runner (hourly)

## Key JSON Files

| File | Purpose | Updated By |
|------|---------|------------|
| `library.json` | Processed files metadata | Backend (save_to_library) |
| `download_queue.json` | YouTube download queue state | Backend (save_queue) |
| `notifications.json` | User notification history | Backend (save_notifications) |
| `metadata_cache.json` | File metadata cache | Backend (save_metadata_cache) |
| `tasks.json` | Active task persistence | Backend (save_tasks_async) |
| `video.json` | Processing configuration | Frontend/Backend |

## Temporary Files

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

## Recent Changes

For detailed changelogs, see:
- **[Backend Changelog](backend_changelog.md)** - Full backend version history
- **[Frontend Changelog](frontend_changelog.md)** - Full frontend version history

### Version Highlights

#### Backend
| Version | Key Changes |
|---------|-------------|
| **0.0.11** | Video extension bug fix, 3-stage file detection, rate limiting improvements, queue control API |
| **0.0.10** | Metadata cache path fix, library scan exclusion logic |
| **0.0.9** | Folder batch processing, library filters, batch status API |
| **0.0.8** | Queue management enhancements, console log panel |
| **0.0.7** | Backend architecture refactoring (core/, utils/, services/ layers) |
| **0.0.6** | Task persistence, background cleanup scheduler, safe file operations |

#### Frontend
| Version | Key Changes |
|---------|-------------|
| **0.0.11** | Cancel All button, force cancellation UI, subfolder support fix |
| **0.0.10** | System info footer, separation icon update |
| **0.0.9** | Playlist support, format preference memory, compact header |
| **0.0.8** | Queue UI, folder processing UI, notification bell |
| **0.0.7** | Notification system, download retry logic, library search |
| **0.0.6** | React Hot Toast integration, settings modal, console panel |

---

## Environment & Dependencies

- **Python**: 3.10+ (UV managed)
- **Backend Version**: 0.0.11 (pyproject.toml)
- **Frontend Version**: 0.0.11 (package.json)
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
├── pyproject.toml          # Python project config (version 0.0.11)
├── requirements.txt        # Python dependencies
├── deno.json               # Deno configuration
├── backend/                # FastAPI backend
│   ├── backend.py          # FastAPI app with startup/shutdown events
│   ├── __main__.py         # Entry point for python -m backend
│   ├── models.py           # Pydantic request/response schemas
│   ├── config.py           # Compatibility layer (re-exports from core/)
│   ├── core/               # Core state and constants
│   │   ├── __init__.py
│   │   ├── state.py        # Global state variables with asyncio locks
│   │   └── constants.py    # File paths and threshold settings
│   ├── routes/             # API endpoint handlers
│   │   ├── __init__.py
│   │   ├── downloads.py    # YouTube download & queue endpoints
│   │   ├── separation.py   # Vocal separation endpoints
│   │   ├── library.py      # Library management endpoints
│   │   └── notifications.py # Notifications & system info
│   ├── services/           # Business logic layer
│   │   ├── __init__.py
│   │   ├── download_service.py  # yt-dlp download logic
│   │   ├── queue_service.py     # Queue processing logic
│   │   ├── separation_service.py # Vocal separation orchestration
│   │   ├── persistence.py       # JSON data persistence layer
│   │   └── cleanup.py           # Background cleanup scheduler
│   ├── utils/              # Utility functions
│   │   ├── __init__.py
│   │   ├── file_ops.py     # Safe file operations
│   │   ├── validation.py   # Input validation
│   │   ├── helpers.py      # General helper functions
│   │   └── async_tools.py  # Async utilities
│   └── modules/            # Core processing modules
│       ├── __init__.py
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
│   ├── package.json        # NPM dependencies (v0.0.11)
│   └── vite.config.js      # Vite configuration
├── data/                   # Persistent data files
│   ├── library.json        # Processed files metadata
│   ├── download_queue.json # Queue state
│   ├── notifications.json  # Notification history
│   ├── tasks.json          # Active task persistence
│   ├── metadata_cache.json # File metadata cache
│   └── video.json          # Processing config
├── download/               # YouTube downloads (user data)
├── nomusic/                # Separated output (user data)
├── uploads/                # Temporary upload folder
├── _temp/                  # General temp files
├── _processing_intermediates/  # Batch processing temp
└── docs/                   # Documentation
    └── ARCHITECTURE.md     # This file
```
