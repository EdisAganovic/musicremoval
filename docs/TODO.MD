# TODO: Music Removal App - Error Handling & Edge Cases

> **Organized by Sprints** - Each sprint represents a focused iteration of ~1-3 days

---

## Sprint 0: Critical Bug Fixes (IMMEDIATE)

**Goal:** Fix issues that cause complete failures or data corruption

- [ ] **FFmpeg Filtergraph Error:** Remove `-c:v copy` when using `-vf` filter, or re-encode video
- [x] **Add FFmpeg existence check** before processing (Done in `download_ffmpeg`)
- [x] **Add input file validation** before processing (Added strict null-checks for `info` and `info_dict`)
- [x] **Handle special characters** in filenames (subfolder and title sanitization implemented)

---

## Sprint 1: Process Timeout & Hanging Prevention

**Goal:** Prevent processes from getting stuck indefinitely

### module_spleeter.py
- [ ] Add 300s timeout to Spleeter commands (per segment)
- [ ] Add try-except for `TimeoutExpired`
- [ ] Continue processing remaining segments if one fails

### module_demucs.py
- [ ] Add 600s timeout to Demucs commands (per segment)
- [ ] Catch `TimeoutExpired` in parallel processor
- [ ] Ensure silence fallback works for timeouts too

### module_processor.py
- [ ] Add 60s timeout to FFmpeg sync adjustment
- [ ] Add 120s timeout to final audio conversion
- [ ] Add 600s timeout to final video creation
- [ ] Add comprehensive try-except-finally blocks for temp file cleanup

### module_ytdlp.py
- [ ] Add 600s timeout per download attempt
- [ ] Add exponential backoff with max 3 retries

### process_manager.py
- [ ] Add default timeout parameter to `tracked_run()`
- [ ] Add logging for timeout events

---

## Sprint 2: FFmpeg Error Handling

**Goal:** Robust FFmpeg execution with clear error messages

- [ ] Catch and parse FFmpeg exit codes
- [ ] Log full FFmpeg stderr output to a debug log file
- [ ] Implement retry logic for transient failures (2 retries)
- [ ] Provide user-friendly error messages (not just stack traces)
- [ ] Handle specific errors:
  - [ ] Input file not found
  - [ ] Codec not available
  - [ ] Disk space insufficient
  - [ ] Permission denied
  - [ ] Invalid filter/graph

---

## Sprint 3: File System & Path Handling

**Goal:** Handle all file system edge cases gracefully

### Validation
- [ ] Check disk space before processing (min 2GB free)
- [ ] Validate input file exists and is readable
- [ ] Ensure output directory exists (create if not)
- [ ] Handle file locking issues (file in use by another process)

### Path Sanitization
- [ ] Handle special characters: `｜`, `:`, `*`, `?`, `"`, `<`, `>`, `|`
- [ ] Handle emojis in filenames
- [ ] Handle very long file paths (> 260 characters on Windows)
- [ ] Handle Unicode characters in filenames
- [ ] Handle spaces in file paths
- [ ] Normalize relative vs absolute paths

### Cleanup
- [ ] Clean up temp files on failure (finally blocks)
- [ ] Verify temp file cleanup on success
- [ ] Handle output file already exists (overwrite vs skip)
- [ ] Handle read-only output directory

---

## Sprint 4: Download & Network Resilience

**Goal:** Reliable downloads with proper error recovery

- [ ] Handle download timeouts (see Sprint 1)
- [ ] Retry failed downloads with exponential backoff
- [ ] Validate downloaded file integrity (checksum or minimum size)
- [ ] Handle partial downloads (resume or redownload)
- [x] Detect and handle rate limiting (Enhanced via impersonate and fallback strategies)
- [x] Handle age-restricted content (Fixed JS challenge solving via Deno config fix)
- [x] Handle playlist vs single video detection (Implemented in `yt-formats` with dedicated views)

---

## Sprint 5: Audio Processing Edge Cases

**Goal:** Handle all audio/video stream variations

### Input Handling
- [ ] Handle videos with no audio track (skip or error gracefully)
- [ ] Handle videos with multiple audio tracks (auto-select by language)
- [ ] Detect unsupported audio codecs (suggest conversion)
- [ ] Handle audio extraction failures

### Duration Edge Cases
- [ ] Handle very short videos (< 1 second)
- [ ] Handle very long videos (> 4 hours)
- [ ] Handle variable frame rate videos

### Quality/Format Edge Cases
- [ ] Handle 4K/8K resolution videos
- [ ] Handle unusual codecs (HEVC, VP9, AV1)
- [ ] Handle corrupted or partially downloaded input files
- [ ] Handle live stream recordings (incomplete files)

---

## Sprint 6: Monitoring & Logging

**Goal:** Comprehensive observability for debugging

### Logging Improvements
- [ ] Add structured logging (JSON format option)
- [ ] Include context in logs (filename, step, timestamp, PID)
- [ ] Add log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] Log FFmpeg full output to separate debug file (`_temp/ffmpeg_debug.log`)
- [ ] Add progress indicators for long operations

### Health Checks
- [ ] Pre-run system check (FFmpeg, disk space, permissions)
- [ ] Output file validation after processing
- [ ] Temp file cleanup verification
- [ ] Add `/api/diagnostics` endpoint improvements

---

## Sprint 7: User Experience

**Goal:** Clear feedback and helpful error messages

### Error Messages
- [ ] Translate technical errors to user-friendly messages
- [ ] Suggest fixes in error messages
- [ ] Provide error codes for support reference
- [ ] Log detailed error info while showing simplified message to user

### Progress Feedback
- [ ] Show progress percentage for FFmpeg operations
- [ ] Show estimated time remaining
- [x] Show current processing step clearly (Updated `download_service.py` with descriptive steps)
- [x] Show file sizes (input/output) (Now displayed in format dropdown and progress hooks)
- [ ] Show audio/video quality info

---

## Backlog: Future Improvements

### Testing Strategy
- [ ] Unit tests for FFmpeg command builder
- [ ] Unit tests for file validation functions
- [ ] Unit tests for path sanitization functions
- [ ] Integration tests with sample videos:
  - [ ] Standard 1080p video with AAC audio
  - [ ] Video with no audio
  - [ ] Video with multiple audio tracks
  - [ ] Video with special characters in filename
  - [ ] 4K video
  - [ ] Very short video
  - [ ] Very long video
- [ ] Test error recovery (simulate failures at each step)
- [ ] Test cleanup after failure

### System Edge Cases
- [ ] Handle concurrent processing (multiple instances running)
- [ ] Handle process interrupted (Ctrl+C, power loss)
- [ ] Cross-platform testing (Windows, macOS, Linux)
- [ ] Handle restricted environments (no temp folder access)

---

## Reference: Critical Issues Matrix

| Module | Issue | Risk | Sprint |
|--------|-------|------|--------|
| module_spleeter.py:68 | No timeout on Spleeter | HIGH | 1 |
| module_demucs.py:75 | No timeout on Demucs | HIGH | 1 |
| module_processor.py:358 | FFmpeg sync no timeout | MEDIUM | 1 |
| module_processor.py:405 | Final conversion no timeout | MEDIUM | 1 |
| module_processor.py:445 | Video creation no timeout | MEDIUM | 1 |
| module_ytdlp.py:133 | Download can hang forever | HIGH | 1 |

---

## Good Practices Already in Place ✅

- ✅ Process manager tracks all subprocess calls via `tracked_run()`
- ✅ Stale process cleanup on startup (`kill_stale_processes()`)
- ✅ Child process cleanup on shutdown (`cleanup_all_children()`)
- ✅ FFmpeg module has error handling for `CalledProcessError`
- ✅ Main entry has `finally` blocks for cleanup
- ✅ Diagnostics endpoint for health checks
