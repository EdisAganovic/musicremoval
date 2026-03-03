# Setup & Troubleshooting Guide

Common issues encountered when setting up DemucsPleeter on new machines.

---

## 1. FFmpeg: Static vs Shared Build (torchcodec / torchaudio)

### Symptom
```
RuntimeError: Could not load libtorchcodec
```
Audio saving/loading fails even though `ffmpeg.exe` works fine from the command line.

### Root Cause
`torchaudio` (2.10+) uses `torchcodec` internally, which requires FFmpeg **shared/dynamic libraries** (`.dll` files like `avcodec-62.dll`, `avformat-62.dll`, `avutil-60.dll`). The commonly installed **static** FFmpeg builds (e.g., `ffmpeg-release-full.7z` from gyan.dev) bundle everything into a single `ffmpeg.exe` with **no DLLs**, so `torchcodec` can't find them.

### Fix
1. Download the **full-shared** Windows build from [BtbN's FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases/latest):
   - File: `ffmpeg-master-latest-win64-gpl-shared.zip`
   - Use the `.zip` version (no 7-Zip needed)
2. Extract to a permanent location, e.g.:
   ```
   %LOCALAPPDATA%\ffmpeg-shared\
   ```
3. Add the `bin` folder to the **user PATH**:
   ```
   %LOCALAPPDATA%\ffmpeg-shared\ffmpeg-master-latest-win64-gpl-shared\bin
   ```
4. Restart the terminal / app.

### How to Verify
```powershell
# Check that DLLs are accessible
where.exe avcodec-62.dll
# Should return the path inside the shared build's bin folder
```

---

## 2. PyTorch CUDA Version Mismatch (Demucs Hangs / Freezes)

### Symptom
- `demucs proba.wav` hangs indefinitely (no output at all)
- `python -c "import torch"` hangs or freezes the entire PC
- Diagnostics panel shows "loading forever"

### Root Cause
Mismatch between the NVIDIA driver's CUDA version (e.g., 13.2) and PyTorch's CUDA runtime (e.g., cu128). While NVIDIA drivers are backward-compatible, very new/experimental CUDA versions can cause driver-level deadlocks, especially on Ampere GPUs (RTX 30-series).

### Fix
1. **Delete** the `.venv` folder manually (Shift+Delete to bypass Recycle Bin)
2. **Delete** the torch cache: `%USERPROFILE%\.cache\torch`
3. Recreate the environment with a **stable** CUDA version:
   ```powershell
   uv venv
   uv pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
   uv pip install -r requirements.txt
   ```

### Recommended CUDA Versions by GPU
| GPU Family | Architecture | CUDA Version | PyTorch Index |
|---|---|---|---|
| RTX 40xx | Ada Lovelace | cu124 | `whl/cu124` |
| RTX 30xx | Ampere | cu121 or cu124 | `whl/cu121` |
| RTX 20xx | Turing | cu121 | `whl/cu121` |
| GTX 10xx | Pascal | cu118 | `whl/cu118` |
| No GPU | CPU only | cpu | `whl/cpu` |

### Verification
```powershell
python -c "import torch; print(torch.cuda.get_device_name(0))"
# Should print GPU name (e.g., "NVIDIA GeForce RTX 3060")
```

---

## 3. Windows Defender Causing Hangs

### Symptom
- First `import torch` takes 5-10 minutes
- App is extremely slow on first launch
- Task Manager shows high CPU from "Antimalware Service Executable"

### Root Cause
Windows Defender scans the ~800MB `torch_cuda.dll` and thousands of small Python files on first access. This can cause massive I/O bottlenecks.

### Fix
Add the project folder to Windows Defender exclusions:
1. **Windows Security** → **Virus & threat protection** → **Manage settings**
2. Scroll to **Exclusions** → **Add or remove exclusions**
3. Add folder: `C:\Users\<username>\Desktop\PYTHON_PROJEKTI_2025\demucspleeter`
4. Also add: `C:\Users\<username>\Desktop\PYTHON_PROJEKTI_2025\demucspleeter\.venv`

---

## 4. Zombie Processes After Crash

### Symptom
- Multiple `python.exe` or `ffmpeg.exe` processes visible in Task Manager after closing the app
- New runs are slow or fail because old processes hold file locks

### Root Cause
When the app is force-closed during a Demucs/Spleeter separation, the child subprocess keeps running.

### Fix (Built-in)
The app now includes a **Process Manager** that:
- **On startup**: Kills stale processes from previous crashes
- **On shutdown**: Kills all tracked child processes
- **Signal handlers**: Ctrl+C triggers graceful cleanup

### Manual Fix
```powershell
# Kill all orphaned processes related to this project
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *demucs*"
taskkill /F /IM ffmpeg.exe
```

Or use the API:
```
POST http://localhost:5170/api/diagnostics/kill-stale
```

---

## 5. Quick Health Check

The app has a built-in diagnostics panel:
1. Open the app in browser
2. Click the **CPU icon** (⚙️) in the header
3. Click **"Diagnostics"**
4. Review all sections (CUDA, packages, FFmpeg, disk space, models)
5. Click **"Run Test"** to verify Demucs can actually separate audio
6. Click **"Copy Report"** to share the full diagnostic output
