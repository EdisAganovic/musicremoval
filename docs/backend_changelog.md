# Backend Changelog

## [0.0.11] - 2026-03-04 🔧

### [Added]
- **Diagnostics API**: New `/api/diagnostics/health` endpoint with comprehensive system checks (CUDA, FFmpeg, packages, disk, models, Demucs import).
- **Live Demucs Test**: `POST /api/diagnostics/test-demucs` runs a 5-second separation test with status polling.
- **Process Manager**: New `services/process_manager.py` — tracks all child subprocesses (Demucs, FFmpeg, Spleeter) and kills them on app shutdown or crash. Prevents zombie `python.exe`/`ffmpeg.exe` processes.
- **Startup Orphan Cleanup**: On launch, automatically kills stale processes left over from previous crashes.
- **Signal Handlers**: SIGINT/SIGTERM now trigger graceful child process cleanup before exit.
- **Process API**: `GET /api/diagnostics/processes`, `POST /api/diagnostics/kill-processes`, `POST /api/diagnostics/kill-stale` for manual process management.
- **FFmpeg Shared DLLs**: New `module_ffmpeg_shared.py` auto-downloads BtbN's FFmpeg shared build (~90MB) on first startup when `torchcodec` is installed. Required for Demucs/torchaudio on Windows. Cached in `ffmpeg_shared/` folder.
- **Troubleshooting Guide**: New `docs/SETUP_TROUBLESHOOTING.md` documenting FFmpeg builds, CUDA mismatches, Defender issues, and zombie processes.

### [Fixed]
- **Diagnostics Timeout**: All heavy checks (torch import, Demucs import, nvidia-smi) now run in a thread pool with individual async timeouts (20s). Prevents the health endpoint from hanging forever on slow machines.
- **Playlist Single Download**: Added `noplaylist: True` to `yt-dlp` options in `download_service.py`. Selecting 1 video from a 50-video playlist no longer downloads all 50.

### [Changed]
- `module_demucs.py`: All `subprocess.run()` calls replaced with `tracked_run()` from process manager.
- `module_spleeter.py`: All `subprocess.run()` calls replaced with `tracked_run()` from process manager.

---
## [0.0.11] - 2026-03-03 ⚙️

### [Fixed]
- **Video Extension Bug**: Fixed issue where video downloads failed at 99% due to incorrect merged file extension detection.
- **Robust File Detection**: Implemented 3-stage fallback (Exact -> Extension Try -> Time modified) to find merged media files.
- **Private/Deleted Video Filtering**: Playlist analysis now automatically skips unavailable videos.
- **Cleaner Filenames**: Stripped `.part` suffixes in `progress_hook` for better UI display.
- **Rate Limiting**: Reduced inter-download delay from 30-50s to 3-7s.
- **Sticky Status**: Fixed 404 error when cancelling tasks from a previous session.

### [Added]
- **Queue Control API**: Implemented `POST /api/queue/stop` to clear pending items.
- **Force Cancel**: Added logic to mark orphaned/stuck tasks as cancelled.

---
## [0.0.10] - 2026-03-03 🐛
- **Stuck N/A Metadata**: Fixed relative vs absolute path in `metadata_cache.json`.
- **Library Scan**: Fixed exclusion logic to show completed files.
