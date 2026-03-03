# TODO: Music Removal App - Error Handling & Edge Cases

## Known Issues (From Logs)

### FFmpeg Filtergraph Error
**Problem:** `Filtering and streamcopy cannot be used together`
- When using `-vf` (video filter) with `-c:v copy` (codec copy), FFmpeg throws an error
- **Fix:** Either remove `-c:v copy` and re-encode video, or remove `-vf` filter if not needed

---

## Error Handling Improvements

### 1. FFmpeg Command Validation
- [ ] Validate FFmpeg command arguments before execution
- [ ] Detect incompatible flag combinations (e.g., `-vf` + `-c:v copy`)
- [ ] Implement a command builder that prevents invalid combinations
- [ ] Add pre-flight check for FFmpeg binary existence and version

### 2. FFmpeg Execution Error Handling
- [ ] Catch and parse FFmpeg exit codes
- [ ] Log full FFmpeg stderr output to a debug log file
- [ ] Implement retry logic for transient failures
- [ ] Provide user-friendly error messages (not just stack traces)
- [ ] Handle specific errors:
  - Input file not found
  - Codec not available
  - Disk space insufficient
  - Permission denied
  - Invalid filter/graph

### 3. File System Error Handling
- [ ] Check disk space before processing
- [ ] Validate input file exists and is readable
- [ ] Ensure output directory exists (create if not)
- [ ] Handle file locking issues (file in use by another process)
- [ ] Clean up temp files on failure
- [ ] Handle special characters in filenames (already an issue with `｜`)

### 4. Network/Download Error Handling
- [ ] Handle download timeouts
- [ ] Retry failed downloads with exponential backoff
- [ ] Validate downloaded file integrity (checksum or size)
- [ ] Handle partial downloads
- [ ] Detect and handle rate limiting

### 5. Audio Processing Errors
- [ ] Handle videos with no audio track
- [ ] Handle videos with multiple audio tracks
- [ ] Detect unsupported audio codecs
- [ ] Handle audio extraction failures
- [ ] Validate audio file before merging

---

## Edge Cases to Handle

### Input Video Edge Cases
- [ ] Video with no audio stream
- [ ] Video with multiple audio streams
- [ ] Video with unusual resolutions (non-standard aspect ratios)
- [ ] Video with variable frame rate
- [ ] Very short videos (< 1 second)
- [ ] Very long videos (> 4 hours)
- [ ] 4K/8K resolution videos
- [ ] Videos with unusual codecs (HEVC, VP9, AV1)
- [ ] Corrupted or partially downloaded input files
- [ ] Live stream recordings (incomplete files)

### File Path Edge Cases
- [ ] Filenames with special characters: `｜`, `:`, `*`, `?`, `"`, `<`, `>`, `|`
- [ ] Filenames with emojis
- [ ] Very long file paths (> 260 characters on Windows)
- [ ] Unicode characters in filenames
- [ ] Spaces in file paths
- [ ] Relative vs absolute path handling

### System Edge Cases
- [ ] No disk space available
- [ ] FFmpeg not installed or not in PATH
- [ ] Wrong FFmpeg version (too old)
- [ ] Concurrent processing (multiple instances running)
- [ ] Process interrupted (Ctrl+C, power loss)
- [ ] Running on different OS (Windows, macOS, Linux)
- [ ] Running in restricted environment (no temp folder access)

### Output Edge Cases
- [ ] Output file already exists (overwrite vs skip)
- [ ] Output directory is read-only
- [ ] Output filename conflicts

---

## Testing Strategy

### Unit Tests
- [ ] Test FFmpeg command builder with various input combinations
- [ ] Test file validation functions
- [ ] Test path sanitization functions
- [ ] Test error parsing functions

### Integration Tests
- [ ] Test full pipeline with sample videos:
  - [ ] Standard 1080p video with AAC audio
  - [ ] Video with no audio
  - [ ] Video with multiple audio tracks
  - [ ] Video with special characters in filename
  - [ ] 4K video
  - [ ] Very short video
  - [ ] Very long video
- [ ] Test error recovery (simulate failures at each step)
- [ ] Test cleanup after failure

### Manual Testing Checklist
- [ ] Download test (if applicable)
- [ ] Audio extraction
- [ ] Audio removal/replacement
- [ ] Video merging
- [ ] Output file validation
- [ ] Temp file cleanup
- [ ] Error message clarity

---

## Monitoring & Observability

### Logging Improvements
- [ ] Add structured logging (JSON format option)
- [ ] Include context in logs (filename, step, timestamp)
- [ ] Add log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] Log FFmpeg full output to separate debug file
- [ ] Add progress indicators for long operations

### Health Checks
- [ ] Pre-run system check (FFmpeg, disk space, permissions)
- [ ] Output file validation after processing
- [ ] Temp file cleanup verification

---

## User Experience Improvements

### Error Messages
- [ ] Translate technical errors to user-friendly messages
- [ ] Suggest fixes in error messages
- [ ] Provide error codes for support reference
- [ ] Log detailed error info while showing simplified message to user

### Progress Feedback
- [ ] Show progress percentage for FFmpeg operations
- [ ] Show estimated time remaining
- [ ] Show current processing step clearly
- [ ] Show file sizes (input/output)

---

## Immediate Action Items

1. **Fix FFmpeg command:** Remove `-c:v copy` when using `-vf` filter, or re-encode video
2. **Add FFmpeg existence check** before processing
3. **Add input file validation** before processing
4. **Add temp file cleanup** on failure
5. **Improve error messages** to be user-friendly
6. **Handle special characters** in filenames (sanitize or quote properly)
