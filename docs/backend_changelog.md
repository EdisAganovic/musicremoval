# Backend Changelog

## [0.0.18] - 2026-08-20 ⚡

### [Fixed]
- **MP3 Output Codec Mismatch**: Fixed invalid audio stream error (`[mp3 @ ...] Invalid audio stream. Exactly one MP3 audio stream is required.`) when exporting separated vocals/instrumentals to MP3. The pipeline now explicitly specifies `-c:a libmp3lame` for MP3 containers rather than passing AAC codec parameters.

### [Added]
- **Silence Removal with Flow Padding**: Added `remove_silence` parameter on separation endpoints (`/separate`, `/separate-file`, `/folder-queue/process`). When active, detects voice/audio energy and trims long silence gaps, keeping a generous 1.0s buffer before and after vocal phrases along with 30ms micro-fades at cut junctions for natural entry and exit.

---

## [0.0.17] - 2026-07-10 🛠️

### [Added]
- **Instrumental/Karaoke output**: New `export_instrumental` option on `/separate`, `/separate-file`, and `/folder-queue/process`. Demucs now runs with `--two-stems vocals` (producing `no_vocals.wav` at no extra compute cost) and Spleeter's existing `accompaniment.wav` is tracked; `module_processor.py` prefers Demucs's instrumental, falls back to Spleeter's, and encodes it as a second output file alongside vocals. Segmented/parallel processing paths concatenate instrumental segments the same way vocal segments are joined.
- **Preview/quick-test mode**: `/separate` and `/separate-file` now accept a `duration` field (already existed on `FolderQueueProcessRequest`, now on `SeparateRequest` too and wired into the upload route), letting a short clip be processed to compare models before running the full file.
- **Bulk separate from Library**: New `POST /api/folder/scan-files` endpoint builds a folder-queue entry directly from an explicit list of file paths (skipping the directory-scan step), reusing the existing `/folder-queue/process` batch machinery so multi-selected library files get the same batch progress tracking as folder processing.
- **Concurrent yt-dlp fragment downloads**: Added `concurrent_fragment_downloads: 4` to yt-dlp options, speeding up DASH/HLS-fragmented formats (common for higher-res YouTube video).
- **GPU-aware Demucs worker count**: `module_processor.py` now forces Demucs segment processing down to 1 worker at a time when CUDA is available (parallel GPU subprocesses were contending for the same VRAM instead of speeding anything up); CPU-only mode keeps the configured worker count.

### [Fixed]
- **Persistence race**: `tasks` dict is now copied before every `json.dump` in `services/persistence.py`, avoiding a possible `RuntimeError: dictionary changed size during iteration` when a background thread mutates `tasks` mid-save. Diagnostic (`diag-*`) test tasks are also now filtered out of persisted `tasks.json` so they stop mixing into real task history.
- **Wrong timestamp clock**: `added_at`/`created_at` fields in `downloads.py` and `separation.py` used `asyncio.get_event_loop().time()` (a monotonic clock) instead of `time.time()` — replaced everywhere this pattern appeared.
- **Progress auto-save**: download progress persistence used to require hitting an *exact* multiple of 20% (`int(progress) % 20 == 0`), which rarely happened with real float progress values; now saves on crossing each 20% threshold.
- **Cancelled downloads mislabeled as failed**: the download queue only checked for `status == "completed"`, so a user-cancelled download fell through to "failed" — now explicitly recognizes `"cancelled"`.
- **Rename didn't update in-memory tasks**: `/rename-file` updated `library.json` and the metadata cache but left the `tasks` dict pointing at the old path/task_id; now updates and re-persists it too.
- **`kill_stale_processes` too broad**: previously killed any `python.exe` whose command line merely contained the app's working-directory substring — could self-kill or kill unrelated Python processes sharing a parent folder. Now requires a specific app marker (demucs/spleeter/module_*); the bare cwd-substring check is restricted to ffmpeg/ffprobe only.
- **Blocking cleanup on the event loop**: `cleanup_temp_files`/`cleanup_metadata_cache` now run via `asyncio.to_thread` from both startup and the periodic scheduler instead of blocking the loop.
- **Leaked temp file**: the mixed-vocals temp WAV in `module_processor.py` is now created inside `_temp/` and added to the tracked cleanup list, instead of leaking into the OS temp folder if the process exits early.

### [Changed]
- **Deduplicated audio-splitting logic**: the identical "split into 600s segments via ffmpeg" code in `module_demucs.py` and `module_spleeter.py` was extracted into `module_ffmpeg.py::split_audio_into_segments`.
- **Deduplicated separation task bookkeeping**: `separate_audio` and `separate_file` in `routes/separation.py` now share one `_create_separation_task` helper instead of two near-identical copies.
- **`process_file` return signature**: now returns `(primary_output_path_or_False, timings, instrumental_output_path_or_None)` instead of a 2-tuple; all callers (`separation_service.py`, `download_service.py`) updated accordingly.
- **Locking documentation**: `core/state.py` now documents the actual scope of its `asyncio.Lock`s (async-only, not cross-thread) instead of implying stronger guarantees than they provide.

---

## [0.0.16] - 2026-05-07 🎯

### [Removed]
- **All impersonation code**: Stripped `ImpersonateTarget`, `remote_components`, `extractor_args` (`player_client`, `n_js_engine`) from `download_service.py`, `downloads.py`, and `module_ytdlp.py`. yt-dlp now relies solely on `cookies.txt` for YouTube authentication.
- **Unused imports**: Removed `is_youtube_url` import from `download_service.py` and `ImpersonateTarget` imports from all files.

### [Fixed]
- **yt-dlp impersonation crash**: Replaced failed `ImpersonateTarget(client='chrome')` approach with simple cookie-based auth — no impersonation needed.
- **"Unsupported client" warnings**: Removed `player_client` string splicing bug. No more `"Skipping unsupported client"` spam.
- **PO Token warnings**: Removed `mweb` client from extractor args, eliminating GVS PO Token requirement warnings.

### [Changed]
- **Cookies-only auth**: `download_service.py` now reads `data/cookies.txt` via `cookiefile` option instead of impersonation. No YouTube-specific overrides.
- **Format fetching simplified**: `downloads.py` playlist and single-video info fetching now uses cookies only, no YouTube-specific extractor args.
- **CLI module cleaned**: `module_ytdlp.py` subprocess commands no longer pass `--extractor-args` or `--remote-components`.

---

## [0.0.15] - 2026-04-27 🔧

### [Added]
- **Folder Batching Resume**: Added `is_file_processed()` check in `module_processor.py` — scans `nomusic/` for previously processed files and auto-deselects them in folder scan results. No redundant re-processing.
- **Shared Audio Segmentation**: Files >10 minutes are now split once and reused across both Demucs and Spleeter passes, eliminating redundant FFmpeg splitting.
- **Random Delay Toggle**: New `GET/POST /api/settings/random-delay` endpoints to enable/disable anti-bot delays between queue downloads. Configurable from frontend.
- **Docker Spleeter Parallel**: Added `docker-compose.yml` with parallel Spleeter container support. Docker Spleeter can run alongside local Spleeter.

### [Fixed]
- **Impersonation Regression**: Rewrote `download_service.py` to consolidate impersonation inside a cleaner `get_ydl_opts()` helper with proper try/except. Removed nested try/except fallback pattern.
- **Spleeter MODEL_PATH**: Removed `MODEL_PATH` environment variable injection from Spleeter commands — was causing path conflicts on some setups.
- **Spleeter Error Noise**: Suppressed verbose stderr output from Spleeter `CalledProcessError` logging.

### [Changed]
- **Dependencies cleaned**: Removed `psutil`, `watchfiles`, `numpy<2.0.0`, `scipy<1.14.0` from `pyproject.toml`. Cleaned `requirements.txt` and `uv.lock`.
- **Python version**: Updated `.python-version` for compatibility.
- **Frontend subfolder fix**: Synced subfolder state handling in `DownloaderTab.jsx` to fix playlist subfolder bypassing custom input.

---

## [0.0.13] - 2026-03-07 🛡️

### [Added]
- **Theme Color Refinement**: Overhauled the backend logging and console colors to align with the new Emerald Green theme.
- **Data Integrity Check**: Added documentation and diagnostic insights for library path mismatches. Identified issues where absolute file paths from external systems (e.g., client's computer) caused library entries to be pruned.
- **Notification Filtering**: Restricted in-app notifications to only show "error" and "warning" types. Routine "success" and "info" messages are now only logged to the console to reduce clutter.

### [Improved]
- **Library Scanning**: Provided instructions for manual library resets (`library.json` and `metadata_cache.json`) to recover from corrupted path data.

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
