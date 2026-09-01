# Audio Splitter Pro

**Version:** 0.0.19 | **Last Updated:** 2026-08-31

A professional AI-powered vocal separation and audio workstation tool with a modern web interface. Remove vocals or background music from any video/audio file using state-of-the-art AI models (Demucs & Spleeter).

![Version](https://img.shields.io/badge/version-0.0.19-emerald)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.129+-green.svg)
![React](https://img.shields.io/badge/react-18.0+-61dafb.svg)

---







## ✨ Key Features

### 🎵 AI Vocal Separation
- **Dual AI Models** — Runs Demucs (htdemucs) and Spleeter, blends outputs for superior quality
- **Model Selection** — Choose Spleeter, Demucs, or Both per job
- **Instrumental / Karaoke Output** — Optionally export the instrumental track alongside vocals, at no extra AI cost (reuses Demucs's `no_vocals`/Spleeter's `accompaniment` stem)
- **Quick Preview Mode** — Process just the first N seconds to compare model quality before running the full file
- **Batch Folder Processing** — Scan an entire folder of media files and process them in bulk
- **Bulk Separate from Library** — Multi-select files in the Library tab and separate them all in one batch
- **Video & Audio Input** — Accepts MP4, MKV, MOV, AVI, WebM, MP3, FLAC, WAV, M4A and more
- **Skip Video Encoding** — Fast mode copies original video stream without re-encoding
- **Long Audio Segmentation** — Auto-splits files >10 minutes, processes in parallel, concatenates results
- **GPU-Aware Worker Scaling** — Automatically avoids contending parallel Demucs workers on the same GPU
- **Cross-Correlation Alignment** — Millisecond-level sync between original audio and separated output
- **Audio Normalization** — EBU R128 loudnorm for consistent volume levels
- **Smart Audio Track Selection** — Auto-selects best language track from multi-language videos

### 📥 YouTube & Web Downloader
- **Multi-Platform** — Download from YouTube, Facebook, Instagram, TikTok, and 1000+ sites via yt-dlp
- **Format Picker** — Browse available resolutions and codecs (H.264, VP9, AV1) with file size estimates
- **Audio / Video Toggle** — One-click switch between MP3 and MP4 download
- **Playlist & Channel Support** — Browse playlist videos with thumbnails, select individually
- **Batch Queueing** — Add multiple videos to queue with one click
- **Subfolder Organization** — Save downloads into named subfolders
- **Auto-Separation** — Automatically run vocal extraction after download completes
- **Subtitle Download** — Fetch subtitles and auto-generated captions
- **Cookie Support** — Authenticated downloads for age-restricted content
- **Duplicate Detection** — Prevents re-downloading the same URL

### 📊 Download Queue
- **Persistent Queue** — Survives app restarts via JSON persistence
- **Sequential Processing** — Downloads one at a time with auto-advance
- **Anti-Bot Random Delay** — Optional 8-15s delay between downloads to avoid rate limiting
- **Cancel All** — Halt all active and pending downloads instantly

### 📚 Media Library
- **Unified View** — All downloads and separated files in one searchable, sortable table
- **Pagination** — Configurable page size (25/50/100/250) keeps large libraries fast to browse
- **Folder Filtering** — Toggle between download and nomusic folders with size info
- **Bulk Operations** — Select multiple files for batch delete or batch vocal separation
- **Right-Click Context Menu** — Play, Rename, Open Folder, Delete, Send to Separation
- **Metadata Display** — Duration, resolution, codec info, and model badges
- **Broken Entry Cleanup** — Auto-prunes entries for files no longer on disk

### 🩺 Diagnostics & Monitoring
- **Health Dashboard** — CUDA, FFmpeg, disk space, model files, package versions at a glance
- **Live Demucs Test** — Generates a test tone and runs actual Demucs to verify end-to-end
- **GPU / CPU Detection** — Alerts when CPU-only PyTorch is installed with step-by-step GPU fix
- **Process Viewer** — List and kill tracked child processes (ffmpeg, demucs, spleeter)
- **Copy Report** — Export diagnostics as markdown for sharing

### 🔔 Notifications & Console
- **In-App Notifications** — Bell icon with unread count; color-coded by type
- **Live Console Viewer** — Real-time backend logs in a floating panel with color-coded entries
- **Auto-Refresh** — Polls for new notifications every 3 seconds

### ⚙️ Infrastructure
- **Auto FFmpeg Download** — Fetches FFmpeg binaries on first run
- **yt-dlp Auto-Update** — Checks for yt-dlp updates before each download
- **Process Management** — Kills all child processes on shutdown to prevent zombies
- **Stale Process Cleanup** — Orphans from crashed runs are killed on startup
- **Background Cleanup** — Hourly removal of temp files >24h old
- **Docker Spleeter Support** — Optionally runs Spleeter via Docker for isolated execution



## 📦 Installation

### Prerequisites

1. **Python 3.11+** with `uv` package manager
2. **NVIDIA GPU** (recommended) with CUDA toolkit for GPU acceleration
3. **Node.js 18+** for frontend development

### Step-by-Step Setup

#### 1. Install UV (Package Manager)

**Windows:**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux/macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. Clone & Setup Environment

```bash
# Navigate to project directory
cd demucspleeter

# Create virtual environment
uv venv --python 3.10

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

#### 3. Install CUDA (Optional but Recommended)

For NVIDIA GPU acceleration:

1. Download CUDA Toolkit: https://developer.nvidia.com/cuda-12-8-0-download-archive
2. Install matching cuDNN for your CUDA version
3. Use the provided shortcut (Windows) or install manually:

**Windows Shortcut:**
```bash
"GPU Fix.bat"
```

**Manual Installation:**
```bash
# First uninstall CPU version
uv pip uninstall torch torchvision torchaudio

# Install GPU version (replace cu128 with your CUDA version)
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

**Check your CUDA version:**

```bash
nvidia-smi
```

#### 4. Install Node.js (Required for Frontend)

**Download Node.js:**

1. Go to https://nodejs.org/
2. Download **LTS version** (18.x or higher)
3. Run installer (accept defaults)

**Verify installation:**

```bash
node --version  # Should show v18.x.x or higher
npm --version   # Should show 9.x.x or higher
```

**Alternative: Use nvm (Node Version Manager)**

Windows (nvm-windows):

```powershell
# Download from: https://github.com/coreybutler/nvm-windows/releases
# Run installer, then:
nvm install 18
nvm use 18
```

Linux/macOS (nvm):

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18
```

#### 5. Install Frontend Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install all dependencies (first time only)
npm install

# This installs:
# - React 18
# - Vite (build tool)
# - Framer Motion (animations)
# - Lucide React (icons)
# - Axios (HTTP client)
# - Tailwind CSS (styling)
```

**Troubleshooting:**

If `npm install` fails:

```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json  # Linux/macOS
rmdir /s /q node_modules del package-lock.json  # Windows

# Reinstall
npm install
```

#### 6. Configure Backend Port

Create `.env` file in `frontend/` directory:

```bash
# frontend/.env
VITE_API_BASE_URL=http://localhost:5170/api
```

**Important:** Change port `5170` to match your backend port if different.

#### 7. Install FFmpeg (Auto-downloaded)

FFmpeg and FFprobe are automatically downloaded on first run to the `backend/modules/` directory.

---

## 🚀 Running the Application

### Option 1: Quick Start (Recommended)

**Run the complete application:**

```bash
# Windows
run_app.bat

# Linux/macOS
./run_app.sh
```

This starts both:

- **Backend**: http://localhost:5170
- **Frontend**: http://localhost:5173

### Option 2: Manual Start (Development)

**Terminal 1 - Backend:**

```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Start backend with hot reload
python -m uvicorn backend.backend:app --reload --port 5170
```

**Terminal 2 - Frontend:**

```bash
# Navigate to frontend directory
cd frontend

# Start development server
npm run dev
```

This gives you:

- **Backend**: http://localhost:5170
- **Frontend**: http://localhost:5173
- **Hot reload**: Changes auto-refresh

### Command Line Interface

#### Download from YouTube

```bash
# Download audio (default: video)
python main.py download "https://youtube.com/watch?v=..."

# Download with custom filename
python main.py download "https://youtube.com/watch?v=..." "MyVideo.mp4"

# Download and auto-separate vocals
python main.py download "https://youtube.com/watch?v=..." --separate
```

#### Separate Vocals

```bash
# Single file
python main.py separate --file "path/to/video.mp4"

# Process entire folder
python main.py separate --folder "path/to/music_folder"

# Limit to first 30 seconds (preview)
python main.py separate --file "song.mp3" --duration 30

# Keep temporary files (debugging)
python main.py separate --file "video.mp4" --temp
```

### Web Interface

#### 1. Single File Separation

1. Go to **Separation** tab
2. Drag & drop file or click to upload
3. Select model: Spleeter, Demucs, or Both (recommended)
4. Optional: enable **Also Export Instrumental** for a karaoke track alongside vocals
5. Optional: enable **Quick Preview** to process only the first N seconds first
6. Click **Start Separation**
7. Wait for processing (progress shown in real-time)
8. Download or play result from Library

#### 2. Folder Batch Processing

1. Go to **Separation** tab
2. Click **Process Folder**
3. Paste folder path (e.g., `C:\Users\Name\Music`)
4. Click **Scan**
5. Uncheck files you don't want to process
6. Click **Start Batch (X files)**
7. Monitor progress in real-time

#### 3. YouTube Downloader

1. Go to **YT Downloader** tab
2. Paste YouTube URL
3. Click **Analyze**
4. Select format (audio/video) and quality
5. Optional: Select subtitles
6. Optional: Enable auto-separate
7. Click **Download Now** or **Add to Queue**

#### 4. Queue Management

1. Go to **YT Downloader** tab
2. View queue panel at bottom
3. Remove unwanted downloads with trash icon
4. Click **Start** to begin queue processing
5. Click **Pause** to pause after current download
6. Click **Clear Done** to remove completed items

#### 5. Library Management

1. Go to **Library** tab
2. **Search**: Type in search bar to filter files
3. **Sort**: Use dropdown to sort by date or duration
4. **Paginate**: Use the page-size selector and prev/next controls for large libraries
5. **Select**: Click checkboxes for bulk operations
6. **Delete**: Select multiple files and click **Delete X**
7. **Bulk Separate**: Select multiple files and click **Separate X** to batch-process them
8. **Play**: Click file icon or name to open with default player
9. **Open Folder**: Click folder icon to open in Explorer
10. **Separate**: Click Layers icon to separate vocals for a single file

#### 6. Notifications

1. Click **bell icon** in top-right corner
2. View all notifications with status colors:
   - 🟢 Green: Success (download/separation complete)
   - 🔴 Red: Error (failed operations)
   - 🟡 Yellow: Warning (partial success)
   - 🔵 Blue: Info (general updates)
3. Click notification to open file directly
4. Click bell icon in panel to mark all as read
5. Click trash icon to clear all notifications

---

## ⚙️ Configuration

### Processing Settings (`video.json`)

Edit `data/video.json` to customize output settings:

```json
{
  "video": {
    "codec": "h264_nvenc",
    "bitrate": "2500k"
  },
  "audio": {
    "codec": "aac",
    "bitrate": "192k"
  },
  "output": {
    "format": "mp4"
  },
  "processing": {
    "demucs_workers": 2
  }
}
```

## 🏗️ Architecture

### Backend (FastAPI + Python)

```
backend/
├── backend.py           # Main FastAPI server entry point
├── config.py            # Global state and shared settings
├── modules/             # AI core and processing logic
│   ├── module_processor.py    # Main separation orchestrator
│   ├── module_demucs.py       # Demucs AI model wrapper
│   ├── module_spleeter.py     # Spleeter AI model wrapper
│   ├── module_ffmpeg.py       # FFmpeg utilities
│   ├── module_ffmpeg_shared.py # Shared DLL downloader
│   ├── module_audio.py        # Audio alignment & mixing
│   └── module_ytdlp.py        # YouTube downloading
├── services/            # Background services
│   └── process_manager.py     # Child process tracking & cleanup
├── routes/              # API Route definitions
│   ├── diagnostics.py         # Health & diagnostic endpoints
│   ├── separation.py          # Vocal removal routes
│   └── library.py             # File management routes
├── tools/               # Windows native utilities
│   └── SpawnWithJob.exe       # Zombie process prevention
data/                    # Persistent state and configuration
├── video.json           # Processing configuration
├── library.json         # Processed files database
├── download_queue.json  # YT download queue
├── notifications.json   # User alerts
└── metadata_cache.json  # File metadata cache
docs/                    # Documentation and roadmap
├── backend_changelog.md # Backend version history
├── frontend_changelog.md # Frontend version history
├── TODO.MD              # Development roadmap
└── ARCHITECTURE.md      # System design
```

### Frontend (React + Vite)

```
frontend/
├── src/
│   ├── App.jsx              # Main app component
│   ├── components/
│   │   ├── SeparationTab.jsx    # File upload & separation
│   │   ├── DownloaderTab.jsx    # YouTube downloader
│   │   ├── LibraryTab.jsx       # File library management
│   │   ├── NotificationBell.jsx # Notification system
│   │   └── DiagnosticsPanel.jsx # System health dashboard
│   └── contexts/
│       └── NotificationContext.jsx  # Notification state
```

### API Endpoints

**Downloads:**

- `POST /api/download` - Start YouTube download
- `POST /api/queue/add` - Add to download queue
- `GET /api/queue` - Get queue status
- `POST /api/queue/*` - Queue management

**Separation:**

- `POST /api/separate` - Upload file for separation (supports `export_instrumental`, `duration` preview)
- `POST /api/separate-file` - Separate existing file (supports `export_instrumental`, `duration` preview)
- `POST /api/folder/scan` - Scan folder for batch processing
- `POST /api/folder/scan-files` - Build a batch queue directly from an explicit file list (used by Library bulk-separate)
- `POST /api/folder-queue/process` - Start batch processing

**Library:**

- `GET /api/library` - Get all processed files
- `POST /api/delete-file` - Delete file from library
- `POST /api/open-file` - Open file with default player
- `POST /api/open-folder` - Open file location in Explorer

**Notifications:**

- `GET /api/notifications` - Get all notifications
- `POST /api/notifications/mark-read` - Mark all as read
- `POST /api/notifications/clear` - Clear all notifications

**Utilities:**

- `GET /api/status/{task_id}` - Get task progress
- `POST /api/download/cancel` - Cancel active download

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "No audio tracks found"

**Cause:** Video has no audio or unsupported format  
**Fix:** Try a different video or convert to MP4 first

#### 2. "CUDA not available"

**Cause:** CUDA toolkit not installed or PyTorch CPU version  
**Fix:**

1. Install CUDA from NVIDIA
2. Reinstall PyTorch with GPU support (see Installation step 3)
3. Check with `python -c "import torch; print(torch.cuda.is_available())"`

#### 3. "Download failed after 3 attempts"

**Cause:** Network issues or YouTube blocking  
**Fix:**

1. Update yt-dlp: `uv pip install --upgrade yt-dlp`
2. Try using cookies: add `--cookies` flag
3. Use a different format

#### 4. "Out of memory" during batch processing

**Cause:** Too many concurrent jobs for available RAM  
**Fix:**

1. Process fewer files at once
2. Close other applications
3. Consider upgrading RAM (Demucs uses ~8GB per job)

#### 5. "File not found in library"

**Cause:** File was moved or deleted externally  
**Fix:**

1. Click refresh button in Library tab
2. Missing files auto-removed on next refresh
3. Check `library.json` for stale entries

#### 6. Backend won't start

**Cause:** Port 8000 already in use  
**Fix:**

```bash
# Windows - find and kill process
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Linux/macOS
lsof -ti:8000 | xargs kill -9
```

---

## 📊 Performance Benchmarks

| File Type   | Duration | GPU (RTX 3060) | CPU (i7-12700K) |
| ----------- | -------- | -------------- | --------------- |
| Music Video | 3:30     | 45 seconds     | 4 minutes       |
| Full Song   | 5:00     | 1 minute       | 6 minutes       |
| Long Mix    | 30:00    | 6 minutes      | 35 minutes      |
| Podcast     | 60:00    | 12 minutes     | 70 minutes      |

_Times include both Spleeter + Demucs processing with alignment_

---

## 📝 Changelog

See [docs/backend_changelog.md](docs/backend_changelog.md) and [docs/frontend_changelog.md](docs/frontend_changelog.md) for detailed version history.

### v0.0.19 (2026-08-31)
- ✅ **Rebrand to Audio Splitter Pro** across frontend, backend, titles, and diagnostic dashboards
- ✅ **Collapsible Folders Sidebar** with dynamic file counts and subfolder management
- ✅ **Instant Drag & Drop** for moving single or multiple files into folders with zero-delay optimistic UI
- ✅ **Disk Folder Auto-Discovery** via `/api/library/folders` with empty subfolder support
- ✅ **Centered Floating Audio Player** with smooth spring animations and full responsive support
- ✅ **High-Performance Library Caching & Fast Traversal** with `os.scandir` iteration and in-memory TTL caching

### v0.0.18 (2026-08-20)
- ✅ Added "Remove Silence" toggle with natural 1.0s lead-in/lead-out flow padding and micro-fades
- ✅ Fixed FFmpeg MP3 output muxing failure by enforcing `-c:a libmp3lame` for MP3 audio exports

### v0.0.17 (2026-07-10)
- ✅ Instrumental/karaoke output option (no extra AI cost)
- ✅ Quick Preview mode for fast model A/B comparison
- ✅ Bulk "Separate Selected" from the Library tab
- ✅ Library pagination
- ✅ GPU-aware Demucs worker scaling + concurrent yt-dlp fragment downloads
- ✅ Fixed persistence race, wrong monotonic timestamps, progress auto-save threshold, cancelled-download mislabeling, stale rename state, over-broad stale-process killing, blocking cleanup on the event loop, and a leaked temp file

### v0.0.14 (2026-05-07)
- ✅ `curl-cffi` integration for Chrome impersonation
- ✅ Fixed `player_client` extraction warnings
- ✅ Graceful impersonation fallbacks

### v0.0.13 (2026-03-16)
- ✅ Emerald Green Theme visual overhaul
- ✅ Data integrity & path mismatch diagnostics
- ✅ Restricted notifications for cleaner UX

### v0.0.12 (2026-03-07)
- ✅ System Diagnostics Dashboard
- ✅ Windows Job Object "Zombie" protection
- ✅ Process Manager for child cleanup
- ✅ FFmpeg Shared DLL auto-download

### v0.0.11 (2026-03-03)
- ✅ "Cancel All" queue management
- ✅ Enhanced playlist extraction
- ✅ Progress persistence fixes

### v0.0.5 (2026-03-02)
- ✅ Production-grade batch processing stability
- ✅ UI follow-process auto-scrolling

### v0.0.1 (2025-02-19)

- Initial release with core separation functionality

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Demucs**: Facebook Research - https://github.com/facebookresearch/demucs
- **Spleeter**: Deezer - https://github.com/deezer/spleeter
- **yt-dlp**: YouTube downloader - https://github.com/yt-dlp/yt-dlp
- **FFmpeg**: Multimedia framework - https://ffmpeg.org/

---

## 💡 Tips & Best Practices

### For Best Separation Quality:

1. Use **Both** models (Spleeter + Demucs)
2. Start with high-quality source files (FLAC > MP3)
3. Ensure files are stereo (not mono)
4. Use GPU acceleration for faster processing

### For Batch Processing:

1. Organize files in dedicated folders
2. Remove unwanted files before starting batch
3. Monitor first file to verify quality
4. Process in small batches (5-10 files) for stability

### For Library Management:

1. Regular cleanup of unwanted files
2. Use search to quickly find specific tracks
3. Bulk delete old/failed processes
4. Backup `library.json` for archival

### System Optimization:

1. Close memory-intensive apps during processing
2. Use SSD for faster temp file I/O
3. Enable GPU acceleration in BIOS
4. Keep drivers updated (NVIDIA/AMD)

---

_**Built with ❤️ using FastAPI, React, and AI**_

_Environment: Python 3.11+ (UV) + Deno 2.5 + Vite/React 18_
