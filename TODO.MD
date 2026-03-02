# TODO - Codebase Improvements & Optimizations

> Last Updated: 2026-03-02

---

## 🚀 HIGH PRIORITY (Performance & Stability)

#### 1. Implement WebSockets for Progress Updates

**Files:** `backend/backend.py`, `frontend/src/components/`
**Current:** HTTP polling every 200ms-1s.
**Optimization:** Replace polling with FastAPI WebSockets (`/ws/status/{task_id}`).

- **Benefit:** Reduces server overhead by 90%, near-zero latency progress bars.

#### 2. Persistent AI Model Loading

**File:** `backend/modules/module_processor.py`, `backend/modules/module_demucs.py`
**Current:** Models load from disk for every single file.
**Optimization:** Implement a "Keep Model Warm" system.

- **Benefit:** Saves 10-20 seconds of load time per file in batch processing.

#### 3. Optimized Library Scanning

**File:** `backend/routes/library.py`
**Current:** Full folder traversal (`os.walk`) on every library tab refresh.
**Optimization:** Implement a database (SQLite) that only updates on file system events.

- **Benefit:** Instant library loading even with 1000+ files.

---

## 🎯 MEDIUM PRIORITY (UX & Features)

---

## 🛠️ LOW PRIORITY (Polish & Housekeeping)

#### 7. Metadata Extraction Refactoring

**File:** `backend/config.py`
**Current:** Multiple ffprobe calls.
**Optimization:** Use `tinytag` or `mutagen` for faster metadata reading where video streams aren't needed.
