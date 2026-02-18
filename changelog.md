# Changelog - 2025-02-19 ⚡

Detailed log of system architecture updates, API enhancements, and frontend logic improvements.

## [Added]

### Backend & Core Logic

- **Deno Bridge Implementation**: Created `modules/module_deno.py` to allow Python-to-Runtime execution of TS/JS.
- **YouTube Metadata API**: New `/api/yt-formats` endpoint using `yt-dlp` to extract remote stream info (thumbnails, titles, available formats).
- **Format-Specific Downloads**: Modified `run_yt_dlp` to support user-defined `format_id` with fallback logic to `bestvideo+bestaudio`.
- **Permanent Deletion**: `/api/delete-file` endpoint added for atomic disk removal and `library.json` state cleanup.
- **Automated Probing**: Post-process metadata extraction via `ffprobe` capturing `bitrate`, `codec_name`, `resolution`, and `duration`.

### Frontend & UI

- **Link Analyzer**: New analysis workflow in `DownloaderTab.jsx` with real-time format dropdown population.
- **Direct Playback System**: Integrated `os.startfile` equivalent shell execution via `/api/open-file` triggered by filename/icon clicks.
- **Deno Status Badge**: Live runtime health check in footer with diagnostic alert modal.
- **Library Tooling**: Added "Copy Path" (clipboard API integration) and "Permanent Delete" action buttons.
- **Process Reset**: `handleReset` state management for one-click workflow restarts.

## [Improved]

- **Yt-dlp Security**: Forced `remote_components: ['ejs:github']` configuration to enable Deno-based JS challenge solvers.
- **Merging Consistency**: Updated Progress Hook to stall at 99% during `FFmpeg` container muxing, hitting 100% only upon filesystem verification.
- **File Naming Convention**: Implemented `nomusic_` prefixing and UUID stripping via `os.path` regex-like logic for cleaner output paths.
- **Polling Logic**: `LibraryTab.jsx` now uses `setInterval` (10s) with atomic state updates to ensure non-blocking UI refreshes.
- **Explorer Selection**: Refactored `subprocess.Popen` with quoted Windows shell execution to fix "Open Folder" reliability and auto-selection.

## [Fixed]

- **NoneType Stat Error**: Added pre-emptive filename detection guards in `main.py` to prevent backend crashes during muxing.
- **JS Challenge Warnings**: Fixed character-array parsing of yt-dlp flags by passing `remote_components` as a properly typed list.
- **Ghost Entries**: Implemented `existing_ids` check in `save_to_library` to prevent duplicate persistence of the same task.

---

_Environment: Python 3.12 (UV managed) + Deno 2.5 + Vite/React_
