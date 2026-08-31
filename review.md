# Code Review & Resolution Status: Audio Splitter Pro

**Audit Date:** 2026-08-31 | **Engine Version:** 0.0.19

---

## 📊 Summary of Issues & Resolution Status

| # | Priority | Category | Description | Status |
|---|:---:|---|---|:---:|
| 1 | **High** | Bug | `load_config` loses `skip_video_encoding` (dict overwrite) | **✅ FIXED** |
| 2 | **Low** | Optimization | `load_config` called twice redundantly per run | **✅ FIXED** |
| 3 | **High** | Bug | Duplicate `@router.delete("/{project_id}")` in `audio_project.py` | **✅ FIXED** |
| 4 | **High** | Security | Unrestricted path validation in `open-file` & `open-folder` | **✅ FIXED** |
| 5 | **High** | Security | Media streaming path traversal protection | **✅ FIXED** |
| 6 | **Medium** | Logic | `TransactionContext.commit()` no-op rollback issue | **✅ FIXED** |
| 7 | **Low** | Stability | 8-char UUID entropy in audio project workspaces | **✅ FIXED** |
| 8 | **High** | Bug | `KeyError` crash in `separation_service.py` (`export_instrumental`, `remove_silence`) | **✅ FIXED** |
| 9 | **Medium** | Stability | `get_full_library` guarded against invalid `[None]` entries | **✅ FIXED** |
| 10 | **Medium** | Logic | `save_to_library` mutating input caller dictionary in-place | **✅ FIXED** |
| 11 | **High** | Security | Restrict `open-file` against launching executable binaries (`.exe`, `.bat`, etc.) | **✅ FIXED** |
| 12 | **High** | Security | Path traversal prevention in `create_folder` and `move_files` | **✅ FIXED** |
| 13 | **Medium** | Logic | Negative lag handling in FFmpeg vocal sync (`atrim` start shift) | **✅ FIXED** |
| 14 | **Low** | Logic | Cache periodic save counter reliability | **✅ FIXED** |
| 15 | **Critical** | Engine | TIGER-DnR model loading & `httpx` compatibility error | **✅ FIXED** |

---

## 🛠️ Detailed Bug & Fix Breakdown

### 1. `load_config` processing dict overwrite
- **File:** [`backend/modules/module_processor.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/modules/module_processor.py#L236-L252)
- **Problem:** Line 246 replaced `config['processing']` with only `{'demucs_workers': ...}`, wiping `skip_video_encoding` and other default keys.
- **Resolution:** Modified `load_config` to perform key-level deep merging of `processing` settings while preserving all defaults.

### 2. Redundant `load_config` call
- **File:** [`backend/modules/module_processor.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/modules/module_processor.py#L865-L875)
- **Problem:** `settings = load_config('data/video.json')` was called twice in the same `process_file` execution.
- **Resolution:** Removed the redundant second call and reused the in-memory `settings` dictionary.

### 3. Duplicate `delete_project` route
- **File:** [`backend/routes/audio_project.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/routes/audio_project.py#L254-L268)
- **Problem:** Two separate `@router.delete("/{project_id}")` declarations existed, causing dead code.
- **Resolution:** Consolidated into a single cleanly handled delete endpoint.

### 4 & 11. `open-file` and `open-folder` Security Hardening
- **File:** [`backend/routes/library.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/routes/library.py#L433-L460)
- **Problem:** `os.startfile(path)` would execute any path supplied by the client without checking for executable extensions or allowed project boundaries.
- **Resolution:** Enforced allowed workspace root validation and blocked executable formats (`.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.msi`).

### 6. `TransactionContext.commit()` implementation
- **File:** [`backend/utils/async_tools.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/utils/async_tools.py#L10-L55)
- **Problem:** `commit()` only set `self.success = True` without executing queued actions.
- **Resolution:** Redesigned `TransactionContext` so `commit()` executes pending actions in sequence and automatically rolls back preceding actions if any step fails.

### 8. `KeyError` risk in queue processor
- **File:** [`backend/services/separation_service.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/services/separation_service.py#L110-L122)
- **Problem:** Direct dictionary indexing `item["export_instrumental"]` crashed on older task queue items.
- **Resolution:** Replaced with safe `.get()` calls (`item.get("export_instrumental", False)` and `item.get("remove_silence", False)`).

### 10. In-place dictionary mutation in `save_to_library`
- **File:** [`backend/services/persistence.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/services/persistence.py#L245-L255)
- **Problem:** Path normalization modified the caller's `task_data` dictionary directly.
- **Resolution:** Added `task_data = dict(task_data)` to clone the dictionary before altering paths.

### 13. Negative lag sync in FFmpeg
- **File:** [`backend/modules/module_processor.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/modules/module_processor.py#L805-L815)
- **Problem:** Negative lag was discarded without trimming the leading offset.
- **Resolution:** Added `atrim=start=...` filter when `lag_ms < 0` to accurately shift audio starting earlier than original.

### 15. TIGER-DnR PyTorch Engine Loading & `httpx` Compatibility
- **Files:** [`pyproject.toml`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/pyproject.toml), [`backend/modules/module_tiger.py`](file:///d:/PYTHON_PROJEKTI_2025/demucspleeter/backend/modules/module_tiger.py)
- **Problem:** Spleeter pinned legacy `httpx==0.19.0`, which broke `huggingface_hub` with `TypeError: Client.__init__() got an unexpected keyword argument 'follow_redirects'`, causing TIGER model downloads to stall indefinitely.
- **Resolution:** Enforced `httpx>=0.24.0` in `pyproject.toml`, upgraded `httpx` to `0.28.1`, and verified native PyTorch TIGER-DnR execution on CUDA (RTX 5070 Ti).

---

## 📁 Component Size & Architecture Tracking

| Component | Lines | Recommendation |
|---|---:|---|
| `LibraryTab.jsx` | 1,559 | Split table, context menu, and folder sidebar into subcomponents |
| `SeparationTab.jsx` | 1,517 | Extract folder queue table and model configuration cards |
| `DownloaderTab.jsx` | 1,334 | Extract queue list and format selector modals |
| `module_processor.py` | 1,090 | Core engine orchestrator (stable) |
| `audio_project.py` | 1,090 | Split into API routes vs. audio DSP rendering pipeline |
