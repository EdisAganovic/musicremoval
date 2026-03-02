# 🚀 DemucsPleeter - Performance & Quality Roadmap

Following the stabilization of the batch processing system, the following high-priority improvements are planned to reach a professional production standard.

---

## 🐛 Critical Error Handling & Stability Issues

### Analysis Date: 2026-03-02

Scanned files for bare `except:`, `global` state issues, file operation risks, and missing validations.

### 1. **Bare Except Clauses - Silent Failures**

**Problem:** 40+ bare `except:` statements swallow all exceptions, hiding critical errors.

**Locations:**

- `backend/config.py`: Lines 108, 130, 172, 210, 220, 275, 294
- `backend/routes/library.py`: Lines 173, 236, 261
- `backend/routes/notifications.py`: Lines 150, 161, 171, 181, 191, 203, 232
- `backend/routes/downloads.py`: Line 246
- `backend/modules/module_ffmpeg.py`: Line 195
- `backend/modules/module_processor.py`: Multiple locations

**Risk:** Debugging impossible; corrupted state; data loss undetected.

**Recommendation:**

```python
# ❌ Bad
try:
    data = json.load(f)
except:
    data = {}

# ✅ Good
try:
    data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError) as e:
    log_error(f"Failed to load {filename}: {e}")
    data = {}
```

---

### 2. **Race Conditions - Shared Global State**

**Problem:** Global dictionaries/lists modified without locks across async/sync boundaries.

**Affected Globals in `backend/config.py`:**

- `tasks: Dict[str, dict]` - Task status tracking
- `download_queue: List[dict]` - Queue management
- `notifications: List[dict]` - Notification list
- `active_downloads: Dict[str, dict]` - Download instances
- `metadata_cache: Dict[str, dict]` - Cache data
- `console_logs: List[dict]` - Log buffer

**Risk:** Data corruption, lost updates, inconsistent UI state during concurrent operations.

**Recommendation:**

```python
# Use asyncio.Lock for all global state mutations
queue_lock = asyncio.Lock()

async def modify_queue():
    async with queue_lock:
        download_queue.append(item)
        save_queue()
```

---

### 3. **File Operation Vulnerabilities**

**Problem:** `os.remove()`, `os.makedirs()`, file writes without proper error handling.

**Locations:**

- `backend/config.py`: Lines 273, 292 (cleanup_temp_files)
- `backend/routes/library.py`: Line 144 (delete from library)
- `backend/modules/module_spleeter.py`: Line 102
- `backend/modules/module_demucs.py`: Lines 111, 128

**Risk:**

- File deleted between `exists()` check and `remove()` call
- Permission errors crash cleanup routines
- Symlink/lock file edge cases

**Recommendation:**

```python
# ✅ Atomic file operations with proper error handling
def safe_remove(filepath: str) -> bool:
    try:
        os.remove(filepath)
        return True
    except (FileNotFoundError, PermissionError, OSError) as e:
        log_warning(f"Failed to remove {filepath}: {e}")
        return False
```

---

### 4. **Missing Input Validation**

**Problem:** User input (URLs, file paths, JSON payloads) not validated before use.

**Locations:**

- `backend/routes/downloads.py`: `get_yt_formats()` - URL validation
- `backend/routes/separation.py`: `separate_audio()` - file upload handling
- `backend/modules/module_processor.py`: `load_config()` - config validation partial

**Risk:** Path traversal, injection attacks, crashes from malformed input.

**Recommendation:**

```python
# Validate and sanitize file paths
from pathlib import Path
import os

def safe_path(user_input: str, base_dir: str) -> Optional[str]:
    try:
        resolved = Path(base_dir).resolve()
        target = (resolved / user_input).resolve()
        if str(target).startswith(str(resolved)):
            return str(target)
    except Exception:
        pass
    return None  # Invalid path
```

---

### 5. **Resource Leaks**

**Problem:** File handles, subprocess, and network connections not properly closed.

**Locations:**

- `backend/config.py`: Multiple `open()` without context managers in error paths
- `backend/modules/module_ffmpeg.py`: Subprocess calls
- `backend/services/download_service.py`: yt-dlp instances

**Risk:** Memory leaks, file handle exhaustion, locked files on Windows.

**Recommendation:**

```python
# ✅ Always use context managers
with open(filepath, 'r') as f:
    data = json.load(f)
# File auto-closed even on exception

# For subprocess
with subprocess.Popen(...) as proc:
    output, error = proc.communicate()
```

---

### 6. **Incomplete Error Recovery**

**Problem:** Partial failures leave system in inconsistent state.

**Scenarios:**

- Download succeeds but library save fails → orphaned files
- Separation partial success → incomplete result_files
- Queue item processing interrupted → stuck in "processing" forever

**Recommendation:**

```python
# Transactional pattern for multi-step operations
def process_with_rollback(task_data):
    backup = create_backup()
    try:
        step1()
        step2()
        commit()
    except Exception as e:
        rollback(backup)
        raise
```

---

### 7. **Missing Timeout Handlers**

**Problem:** Network requests, subprocess calls, file operations have no timeouts.

**Locations:**

- `backend/modules/module_ytdlp.py`: YouTube downloads
- `backend/modules/module_ffmpeg.py`: FFmpeg processing
- `backend/services/download_service.py`: yt-dlp extraction

**Risk:** Infinite hangs on slow/unresponsive resources.

**Recommendation:**

```python
# Add timeouts to all blocking operations
import asyncio

async def download_with_timeout(url: str, timeout: int = 3600):
    try:
        return await asyncio.wait_for(
            run_yt_dlp(url),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise Exception(f"Download timeout after {timeout}s")
```

---

### 8. **Data Directory Migration - Incomplete**

**Problem:** JSON files moved to `data/` but `library.json` reference added without the file existing.

**Location:** `backend/config.py` Line 11: `LIBRARY_FILE = "data/library.json"`

**Risk:** First save attempt fails if `data/` directory doesn't exist.

**Recommendation:**

```python
# Ensure data directory exists on app startup
def init_data_directory():
    os.makedirs("data", exist_ok=True)
    for file in ["library.json", "download_queue.json",
                 "notifications.json", "metadata_cache.json"]:
        path = f"data/{file}"
        if not os.path.exists(path):
            with open(path, 'w') as f:
                json.dump([], f)  # or {} for dicts
```

---

## ✅ Completed (v0.0.5 - 2026-03-02)

### 🏗️ Batch Scaling & Stability

- **Fixed Polling Race Condition**: Parent batch now tracks successes/failures in memory, preventing "0% complete" UI errors.
- **Persistent Counters**: Batch status no longer disappears after individual file tasks are cleaned up.
- **Fixed NameErrors**: Resolved missing `save_to_library` and `filename` UnboundLocalErrors in the backend worker.
- **Queue Synchronization**: Backend now correctly processes only the files explicitly selected in the UI list.

### ✨ UI & User Experience

- **Loading Status**: Added "Scanning..." state with spinner for folder scanning.
- **Intelligent Scrolling**: Fixed the "jumping scrollbar" bug; the list now auto-scrolls only to the _current_ processing file.
- **Input Locking**: Folder path is now disabled while scanning to prevent configuration conflicts.

### 🔧 API Enhancements

- **Task Status Polling**: Implemented the missing `/api/status/{task_id}` endpoint for per-file progress tracking.
- **UTF-8 Support**: Improved emoji support in the Python console logs for better cross-platform compatibility.

### 📁 Project Organization

- **Documentation**: Moved all `.md` files to `docs/` folder
- **Data Files**: Moved JSON data files to `data/` folder with updated path references

_Last Updated: 2026-03-02_
_Current Version: 0.0.5 (Production Stable Batching)_

---

## 🏎️ 1. Performance: Model Warmup Optimization

- **Goal**: Reduce per-file overhead by avoiding model reloads.
- **Tasks**:
  - [ ] Implement a **Global Model Manager** class to keep Spleeter/Demucs in memory.
  - [ ] Replace `subprocess.run` calls with direct Python module imports for AI models.
  - [ ] **Impact**: Estimated 70% reduction in processing time for batch files.

## 🚦 2. Concurrency: Hardware-Aware Worker Queue

- **Goal**: Prevent GPU/CPU OOM (Out of Memory) crashes.
- **Tasks**:
  - [ ] Implement an `asyncio.Queue` system for separation tasks.
  - [ ] Limit concurrent processes to 1 (or 2 for high-end GPUs).
  - [ ] **Impact**: Stable background processing even with ultra-large batches.

## 💾 3. State Persistence: "Restart Proof" Tasks

- **Goal**: Prevent data loss after app restarts or crashes.
- **Tasks**:
  - [ ] Persist the global `tasks` dictionary to `tasks.json` on every change.
  - [ ] Implement "Resume" logic on backend startup to re-attach to unfinished tasks.
  - [ ] **Impact**: Users never lose batch progress after a code edit or power loss.

## 🧹 4. Maintenance: Automated Cleanup

- **Goal**: Maintain healthy disk space without manual intervention.
- **Tasks**:
  - [ ] Add a background "Garbage Collector" to prune `_temp` files older than 2 hours.
  - [ ] Auto-cleanup empty folders in `spleeter_out` and `demucs_out` after final mix.
  - [ ] **Impact**: Set-and-forget reliability for long-term server usage.
