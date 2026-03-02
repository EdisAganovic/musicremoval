# Backend Refactoring Plan

This document tracks refactoring opportunities identified across the codebase.

---

## Completed Refactoring ✅

### `backend/config.py` Modularization (v0.0.6)

The file was 900+ lines with mixed responsibilities. It has been split into:

- `backend/core/constants.py` - File paths and threshold settings
- `backend/core/state.py` - Global state variables and asyncio locks
- `backend/utils/file_ops.py` - Safe file system operations
- `backend/utils/validation.py` - Path sanitization and URL validation
- `backend/utils/async_tools.py` - TransactionContext, timeouts, backup utilities
- `backend/services/persistence.py` - JSON data loading/saving logic
- `backend/services/cleanup.py` - Periodic background cleanup tasks

### Code Deduplication (v0.0.7)

- Created `backend/utils/helpers.py` with shared `format_duration` function
- Enhanced `utils/validation.sanitize_filename` with `max_length` parameter
- Removed duplicate `sanitize_filename` from `module_ytdlp.py`

### Service Layer Separation (v0.0.7)

- Created `backend/services/separation_service.py`
- Moved `run_separation` from routes to service layer
- Routes now delegate to services (proper separation of concerns)

---

## Future Refactoring (Optional)

### Large Module: `module_processor.py` - LOW PRIORITY

**Issue:** At 632 lines, this file handles multiple responsibilities:
- Config loading (`load_config`)
- File type detection (`is_audio_file`, `is_video_file`)
- Main orchestration (`process_file`)
- Temp file management

**Potential future split:**
- `backend/processor/config.py` - Config loading/validation
- `backend/processor/file_utils.py` - File type helpers
- Keep orchestration in `module_processor.py`

**Note:** Consider only if the module becomes difficult to maintain.

---

## New Files Created

| File | Purpose | Version |
|------|---------|---------|
| `backend/utils/helpers.py` | Shared helper functions | v0.0.7 |
| `backend/services/separation_service.py` | Vocal separation business logic | v0.0.7 |