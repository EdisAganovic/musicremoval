# 🚀 DemucsPleeter - Performance & Quality Roadmap

Following the stabilization of the batch processing system, the following high-priority improvements are planned to reach a professional production standard.

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

## 🧹 6. Maintenance: Automated Cleanup

- **Goal**: Maintain healthy disk space without manual intervention.
- **Tasks**:
  - [ ] Add a background "Garbage Collector" to prune `_temp` files older than 2 hours.
  - [ ] Auto-cleanup empty folders in `spleeter_out` and `demucs_out` after final mix.
  - [ ] **Impact**: Set-and-forget reliability for long-term server usage.

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

_Last Updated: 2026-03-02_
_Current Version: 0.0.5 (Production Stable Batching)_
