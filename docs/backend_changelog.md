# Backend Changelog

## [0.0.13] - 2026-03-07 🛡️

### [Added]
- **Theme Color Refinement**: Overhauled the backend logging and console colors to align with the new Emerald Green theme.
- **Data Integrity Check**: Added documentation and diagnostic insights for library path mismatches. Identified issues where absolute file paths from external systems (e.g., client's computer) caused library entries to be pruned.
- **Notification Filtering**: Restricted in-app notifications to only show "error" and "warning" types. Routine "success" and "info" messages are now only logged to the console to reduce clutter.

### [Improved]
- **Library Scanning**: Provided instructions for manual library resets (`library.json` and `metadata_cache.json`) to recover from corrupted path data.

---

## [0.0.12] - 2026-03-07 🛡️

### [Added]
- **Zombie Process Protection**: Integrated Windows Job Object management (`SpawnWithJob.exe`) to ensure child processes (Demucs, FFmpeg, Spleeter) are terminated even if the backend crashes.
- **Enhanced Logging**: Integrated process failure logging to `log.txt` via the C# wrapper for better post-mortem analysis.

### [Fixed]
- **Job Limit Errors**: Resolved "Failed to set job limits" (Error 87) on Windows systems.
- **Sync Performance**: Optimized synchronization check logic to prevent hanging during the final verification step.

### [Changed]
- **I/O Optimization**: Refined asynchronous I/O and file handle management to prevent disk cache saturation.
- **Version Alignment**: Synced backend version string to `0.0.12`.

---


### [Added]
- **Diagnostics API**: New `/api/diagnostics/health` endpoint with comprehensive system checks (CUDA, FFmpeg, packages, disk, models, Demucs import).
- **Live Demucs Test**: `POST /api/diagnostics/test-demucs` runs a 5-second separation test with status polling.
- **Process Manager**: New `services/process_manager.py` — tracks all child subprocesses (Demucs, FFmpeg, Spleeter) and kills them on app shutdown or crash. Prevents zombie `python.exe`/`ffmpeg.exe` processes.
- **Startup Orphan Cleanup**: On launch, automatically kills stale processes left over from previous crashes.
- **Signal Handlers**: SIGINT/SIGTERM now trigger graceful child process cleanup before exit.
- **Process API**: `GET /api/diagnostics/processes`, `POST /api/diagnostics/kill-processes`, `POST /api/diagnostics/kill-stale` for manual process management.
- **FFmpeg Shared DLLs**: New `module_ffmpeg_shared.py` auto-downloads BtbN's FFmpeg shared build (~90MB) on first startup when `torchcodec` is installed. Required for Demucs/torchaudio on Windows. Cached in `ffmpeg_shared/` folder.
- **Troubleshooting Guide**: New `docs/SETUP_TROUBLESHOOTING.md` documenting FFmpeg builds, CUDA mismatches, Defender issues, and zombie processes.
- **URL Normalization**: Added `normalize_youtube_url` helper in `routes/downloads.py` to handle `youtu.be` links and strip `si=` tracking parameters.
- **Codec Visibility**: Added short codec names (e.g., `[avc1/mp4a]`, `[vp9]`) to format selection labels for better clarity.

### [Fixed]
- **Diagnostics Timeout**: All heavy checks (torch import, Demucs import, nvidia-smi) now run in a thread pool with individual async timeouts (20s). Prevents the health endpoint from hanging forever on slow machines.
- **Playlist Single Download**: Added `noplaylist: True` to `yt-dlp` options in `download_service.py`. Selecting 1 video from a 50-video playlist no longer downloads all 50.
- **NoneType Crash Shield**: Added strict null-checks in `download_service.py` (progress hook) and `downloads.py` API routes. Prevents server-side crashes or "stuck" UI spinners when `yt-dlp` returns empty metadata objects.
- **Deno Challenge Solver**: Removed unsupported `allowJs: true` option from `deno.json`. Fixes `yt-dlp` crashing on JS challenges when using Deno as the runtime.
- **YouTube Format Fallback**: Extractor now automatically falls back to standard extraction if the primary impersonated client fails.

### [Changed]
- **Comprehensive Process Tracking**: Coverage of `tracked_run` extended to `module_ffmpeg.py`, `module_ytdlp.py`, `module_processor.py`, and `module_deno.py` ensure ALL backend subprocesses (yt-dlp, FFmpeg, Deno) are managed.
- **Aggressive Format Filtering**: Dropdown now skips phantom streams without size info or those using `m3u8` protocols, greatly cleaning up the resolution list.
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
