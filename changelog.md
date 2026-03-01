# Changelog

## [0.0.3] - 2026-03-01 ⚡

Major UX improvements, playlist support, and configuration centralization.

### [Added]

#### YouTube Downloader

- **Playlist/Channel Download Support**: Full playlist and channel download capability
  - Auto-detects playlist/channel URLs (`/playlist?list=`, `/@channel`, `/channel/`)
  - Displays all videos with thumbnails, titles, and duration
  - Select/deselect individual videos
  - Select All / None buttons for quick selection
  - Confirmation modal before adding to queue ("Are you sure you want to download X videos?")
  - Batch queue addition via `/api/queue/add-batch` endpoint
  - Supports: Playlists, Channels, Mixes, Single videos

- **Video ID Display**: Shows YouTube video ID in brackets for easy identification
  - Format: `[dQw4w9WgXcQ] Video Title`
  - Helps users verify correct video before download

- **Remember Format Preference**: Checkbox to save selected format per video
  - Stores in localStorage: `lastVideoId` and `lastSelectedFormat`
  - Auto-restores saved format when re-analyzing same video
  - Shows "✓ Saved format restored" indicator
  - Toggle on/off with checkbox

- **Format File Size Preview**: Shows estimated file size in format dropdown
  - Format: `1080p (245.3 MB)`
  - Helps users make informed quality/size decisions

#### Library

- **Folder Filter System**: Filter library by source folder
  - "All Files" - Shows everything
  - "Download" - Shows only downloaded files (red highlight)
  - "NoMusic" - Shows only separated files (emerald highlight)
  - Quick filter buttons always visible

- **Open Folder Quick Actions**: One-click folder access
  - "Open Download" button - Opens download folder
  - "Open NoMusic" button - Opens separated files folder
  - Always visible in library header

- **Smart Separate Button**: Hides for already-separated files
  - Shows separate button only for download folder files
  - Hides for nomusic files (already processed)

#### Configuration

- **Centralized Port Configuration**: Single source of truth for backend port
  - `.env` file: `VITE_API_BASE_URL=http://localhost:5170/api`
  - API client layer reads from environment
  - No more hardcoded URLs in components
  - Easy port changes: edit `.env` and restart

- **API Client Layer**: Centralized API communication
  - `frontend/src/api/index.js` with organized endpoints
  - Axios instance with 30s timeout
  - Request/response interceptors for logging
  - Organized by feature: `libraryAPI`, `separationAPI`, `downloadAPI`, `queueAPI`, `notificationsAPI`

### [Changed]

#### UI/UX

- **Compact Header**: Reduced header size by ~50%
  - Logo: 64px → 20px
  - Title: 36px → 24px
  - Subtitle removed for cleaner look
  - Tighter spacing throughout

- **Smoother Tab Transitions**: Faster, cleaner animations
  - Duration: 0.3s → 0.15s (2x faster)
  - Removed flying animation (y-axis movement)
  - Simple opacity fade only
  - No scale effect

- **Removed Redundant Header**: YT Downloader tab header removed
  - Removed large YouTube icon
  - Removed "YouTube Downloader" title
  - Removed "Advanced Format Selection Control" subtitle
  - More space for actual content

- **Library Table Layout**: Replaced card layout with compact table
  - 2-3x more files visible
  - Organized columns: File, Duration, Quality, Actions
  - Smaller icons and fonts
  - Cleaner visual hierarchy

### [Fixed]

- **Port Configuration**: All hardcoded `localhost:8000` URLs replaced
  - Changed 25+ instances to use API client layer
  - All components now use centralized configuration
  - No more CORS errors from port mismatch

- **Folder Name Mismatch**: Corrected "downloads" → "download"
  - Filter logic updated
  - Button labels updated
  - Open folder actions updated

### [Technical]

- **Backend Playlist API**: New `/api/yt-formats` logic
  - Detects playlist/channel URLs automatically
  - Returns `{is_playlist: true, videos: [...], video_count: X}`
  - `format_duration()` helper for readable timestamps

- **Backend Batch Queue API**: New `/api/queue/add-batch` endpoint
  - Adds multiple videos in single request
  - Returns `{added: X, status: "queued"}`
  - Efficient for large playlists

- **Documentation**: Created `PORT_CONFIG.md`
  - Explains how to change backend port
  - Single source of truth for configuration

---

## [0.0.2] - 2026-03-01 ⚡

Major feature expansion with queue management, batch processing, notifications, and production-ready reliability improvements.

### [Added]

#### Backend & Core Features

- **Download Queue System**: Full queue management with `/api/queue/*` endpoints for batch download scheduling
  - Add to queue, remove from queue, clear completed
  - Start/stop queue processing
  - Persistent queue storage (`download_queue.json`)
  - Auto-resume pending downloads on startup

- **Folder Batch Processing**: Process entire folders with `/api/folder-queue/*` endpoints
  - Scan folder and return file list with metadata
  - Interactive queue UI (select/deselect, remove files)
  - Real-time progress tracking per file
  - Concurrent batch status polling

- **In-App Notification System**: Complete notification infrastructure
  - Persistent notifications storage (`notifications.json`)
  - `/api/notifications` endpoints (get, mark read, clear)
  - Frontend notification bell with unread counter
  - Auto-notifications for: download complete, separation complete, errors
  - Test notification endpoint for debugging

- **Download Retry Logic**: Exponential backoff for failed downloads
  - 3 retry attempts with increasing delay (2s, 4s, 8s)
  - User-friendly retry status in UI
  - Automatic recovery from transient network errors

- **Auto Disk Cleanup**: Automatic temporary file cleanup on startup
  - Cleans: `_temp`, `uploads`, `spleeter_out`, `demucs_out`, `_processing_intermediates`
  - Removes files older than 24 hours
  - Configurable retention period
  - Cleanup report in console

- **Duplicate Detection**: Prevent downloading same content twice
  - Check library for existing files before download
  - Returns duplicate warning with existing file path

- **Quality Presets System**: Pre-configured output quality settings
  - **Fast**: Small size, copy codec, 128k audio
  - **Balanced**: h264_nvenc, 2500k, 192k audio (default)
  - **Quality**: hevc_nvenc, 8000k, 256k audio
  - `/api/presets` endpoints for getting/setting presets
  - Stored in `video.json` with preset metadata

- **Library Search & Bulk Operations**: Advanced library management
  - Real-time search by filename or duration
  - Sort by date or duration
  - Multi-select with checkboxes
  - Bulk delete with confirmation
  - Select all / Deselect all buttons

#### Frontend & UI

- **Queue UI in Downloader**: Visual queue management
  - File list with status indicators
  - Progress bars for each download
  - Remove from queue button
  - Start/Pause queue controls
  - Auto-separate toggle per download

- **Folder Processing UI**: Dedicated folder processing workflow
  - Manual folder path input (Windows path paste)
  - File preview with metadata (duration, resolution)
  - Checkbox selection for each file
  - Remove unwanted files before processing
  - Batch progress dashboard

- **Notification Bell Component**: Real-time notification display
  - Unread count badge
  - Dropdown panel with all notifications
  - Color-coded by type (success/error/warning)
  - Click to open file directly
  - Mark all/individual as read
  - Clear all notifications

- **Library Enhancements**: Improved library management
  - Search bar with instant filtering
  - Sort dropdown (date/duration)
  - Checkboxes for bulk selection
  - Bulk delete button with count
  - Visual highlighting for selected items

- **Stop Download Button**: Cancel active downloads
  - Red stop button in download status card
  - Graceful cancellation with cleanup
  - Updates task status to "cancelled"

### [Improved]

- **Non-Blocking Downloads**: All yt-dlp operations run in thread pool executor
  - UI remains responsive during downloads
  - Multiple concurrent downloads supported
  - Progress updates via polling

- **Clean Progress Display**: Removed ANSI color codes from frontend status
  - Shows only percentage: "Downloading: 45%"
  - No more `[0;94m` escape codes

- **Startup Experience**: Enhanced backend startup output
  - Colored section headers
  - Queue resumption status
  - Cleanup report
  - Ready status confirmation

- **Video Default**: Changed downloader default format to video (was audio)

- **Library Icons**: Removed hover play overlay, simplified to static icons

### [Fixed]

- **Uvicorn Hot Reload**: Excluded temp directories from file watching
  - Prevents crashes when `demucs_out`, `spleeter_out` are deleted
  - `--reload-exclude` for all temp folders

- **Batch Processing Stall**: Fixed "Start Batch" button not triggering processing
  - Now calls `handleStartBatchProcessing` correctly
  - Shows selected file count in button

- **Queue Persistence**: Queue survives backend restarts
  - Loads from `download_queue.json` on startup
  - Auto-starts pending downloads

### [Refactored]

- **Backend Logging**: Set uvicorn to `--log-level warning`
  - Hides INFO spam from console
  - Shows only warnings and errors
  - Custom colored output for important events

- **run_app.bat**: Updated to include hot reload with excludes
  - Single command to start both frontend and backend
  - Proper log level configuration

### [Technical Debt]

- **Memory Management**: Identified need for concurrent job limiting based on RAM
- **ETA Calculation**: Progress estimation for batch processing (future)
- **Hardware Acceleration**: Auto-detection for FFmpeg encoders (future)

---

## [0.0.1] - 2025-02-19 ⚡

Initial release with core vocal separation functionality.

### [Added]

#### Backend & Core Logic

- **Deno Bridge Implementation**: Created `modules/module_deno.py` to allow Python-to-Runtime execution of TS/JS.
- **YouTube Metadata API**: New `/api/yt-formats` endpoint using `yt-dlp` to extract remote stream info (thumbnails, titles, available formats).
- **Format-Specific Downloads**: Modified `run_yt_dlp` to support user-defined `format_id` with fallback logic to `bestvideo+bestaudio`.
- **Permanent Deletion**: `/api/delete-file` endpoint added for atomic disk removal and `library.json` state cleanup.
- **Automated Probing**: Post-process metadata extraction via `ffprobe` capturing `bitrate`, `codec_name`, `resolution`, and `duration`.

#### Frontend & UI

- **Link Analyzer**: New analysis workflow in `DownloaderTab.jsx` with real-time format dropdown population.
- **Direct Playback System**: Integrated `os.startfile` equivalent shell execution via `/api/open-file` triggered by filename/icon clicks.
- **Deno Status Badge**: Live runtime health check in footer with diagnostic alert modal.
- **Library Tooling**: Added "Copy Path" (clipboard API integration) and "Permanent Delete" action buttons.
- **Process Reset**: `handleReset` state management for one-click workflow restarts.

### [Improved]

- **Yt-dlp Security**: Forced `remote_components: ['ejs:github']` configuration to enable Deno-based JS challenge solvers.
- **Merging Consistency**: Updated Progress Hook to stall at 99% during `FFmpeg` container muxing, hitting 100% only upon filesystem verification.
- **File Naming Convention**: Implemented `nomusic_` prefixing and UUID stripping via `os.path` regex-like logic for cleaner output paths.
- **Polling Logic**: `LibraryTab.jsx` now uses `setInterval` (10s) with atomic state updates to ensure non-blocking UI refreshes.
- **Explorer Selection**: Refactored `subprocess.Popen` with quoted Windows shell execution to fix "Open Folder" reliability and auto-selection.

### [Fixed]

- **NoneType Stat Error**: Added pre-emptive filename detection guards in `main.py` to prevent backend crashes during muxing.
- **JS Challenge Warnings**: Fixed character-array parsing of yt-dlp flags by passing `remote_components` as a properly typed list.
- **Ghost Entries**: Implemented `existing_ids` check in `save_to_library` to prevent duplicate persistence of the same task.

### [Refactored & Cleaned]

- **Folder Unification**: Reverted all download logic to use the singular `download` directory for consistency across CLI and GUI.
- **Codebase Purge**: Removed redundant `src` skeleton and diagnostic `deno_hello.ts` files.
- **Git Shielding**: Optimized `.gitignore` to strictly exclude local state (`library.json`), uploaded assets, and large media formats (`*.webm`, `*.mkv`).

---

_Environment: Python 3.10 (UV managed) + Deno 2.5 + Vite/React_
_Feature Release: Queue System, Batch Processing, Notifications, Auto-Cleanup_
