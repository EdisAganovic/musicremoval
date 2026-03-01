# Demucs & Spleeter Vocal Extractor

**Version:** 0.0.2 | **Last Updated:** 2026-03-01

A professional AI-powered vocal separation tool with a modern web interface. Remove vocals or background music from any video/audio file using state-of-the-art AI models (Demucs & Spleeter).

![Version](https://img.shields.io/badge/version-0.0.2-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.100+-green.svg)
![React](https://img.shields.io/badge/react-18.0+-61dafb.svg)

---

## ✨ Key Features

### 🎯 Core Functionality
- **Dual AI Models**: Combines Demucs (htdemucs) and Spleeter for best-in-class separation
- **Smart Audio Alignment**: Automatic cross-correlation alignment for perfect sync
- **Long Audio Segmentation**: Auto-splits files >10 minutes for reliable processing
- **Multi-Track Support**: Handles videos with multiple audio tracks (auto-select by language)
- **GPU Acceleration**: Full CUDA support for 5-10x faster processing

### 🚀 New in v0.0.2

#### Queue System
- **Download Queue**: Schedule multiple YouTube downloads
- **Batch Folder Processing**: Process entire folders of media files
- **Queue Management**: Start, pause, remove from queue
- **Persistent Queue**: Survives app restarts

#### Notifications
- **In-App Notifications**: Real-time alerts for all operations
- **Smart Notifications**: Download complete, separation done, errors
- **Notification History**: View all past notifications with unread counter

#### Reliability
- **Auto-Retry Downloads**: 3 retry attempts with exponential backoff
- **Auto-Cleanup**: Removes temp files older than 24 hours
- **Duplicate Detection**: Warns before downloading duplicate content

#### Quality & Control
- **Quality Presets**: Fast, Balanced, High Quality presets
- **Output Configuration**: Customizable codec, bitrate, format
- **Search & Filter**: Find files in library by name or duration
- **Bulk Operations**: Multi-select and batch delete

#### UI/UX
- **Modern Dark Theme**: Beautiful glassmorphism design
- **Responsive Layout**: Works on desktop and tablet
- **Real-Time Progress**: Live progress bars and status updates
- **Keyboard Shortcuts**: Quick actions with hotkeys

---

## 📦 Installation

### Prerequisites

1. **Python 3.10+** with `uv` package manager
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
3. Install GPU 版 PyTorch:

```bash
# First uninstall CPU version
uv pip uninstall torch torchvision torchaudio

# Install GPU version (replace cu130 with your CUDA version)
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
```

**Check your CUDA version:**
```bash
nvidia-smi
```

#### 4. Install FFmpeg (Auto-downloaded)

FFmpeg and FFprobe are automatically downloaded on first run to the `modules/` directory.

---

## 🚀 Usage

### Quick Start (Recommended)

**Run the complete application:**

```bash
# Windows
run_app.bat

# Linux/macOS
./run_app.sh
```

This starts both:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173

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
4. Click **Start Separation**
5. Wait for processing (progress shown in real-time)
6. Download or play result from Library

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
4. **Select**: Click checkboxes for bulk operations
5. **Delete**: Select multiple files and click **Delete X**
6. **Play**: Click file icon or name to open with default player
7. **Open Folder**: Click folder icon to open in Explorer
8. **Separate**: Click Layers icon to separate vocals

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

### Quality Presets (`video.json`)

Edit `video.json` to customize output quality:

```json
{
  "presets": {
    "fast": {
      "label": "Fast (Small Size)",
      "video": { "codec": "copy", "bitrate": null },
      "audio": { "codec": "aac", "bitrate": "128k" }
    },
    "balanced": {
      "label": "Balanced (Recommended)",
      "video": { "codec": "h264_nvenc", "bitrate": "2500k" },
      "audio": { "codec": "aac", "bitrate": "192k" }
    },
    "quality": {
      "label": "High Quality (Large Size)",
      "video": { "codec": "hevc_nvenc", "bitrate": "8000k" },
      "audio": { "codec": "aac", "bitrate": "256k" }
    }
  },
  "current_preset": "balanced"
}
```

### Preset Descriptions

| Preset | Video Codec | Bitrate | Audio | Best For |
|--------|-------------|---------|-------|----------|
| **Fast** | Copy (no re-encode) | N/A | 128k | Quick previews, small files |
| **Balanced** | h264_nvenc (GPU) | 2500k | 192k | Everyday use (recommended) |
| **Quality** | hevc_nvenc (GPU) | 8000k | 256k | Archival, high-quality output |

### Supported Formats

**Video Input:**
- MP4, MKV, MOV, AVI, FLV, WEBM, WMV

**Audio Input:**
- MP3, WAV, FLAC, AAC, OGG, M4A, WMA

**Output:**
- Video: MP4 (default), MKV, MOV (configurable)
- Audio: MP3 (from YouTube), WAV, FLAC, M4A

---

## 🏗️ Architecture

### Backend (FastAPI + Python)

```
backend/
├── main.py              # FastAPI server, all API endpoints
├── modules/
│   ├── module_processor.py    # Main separation orchestrator
│   ├── module_demucs.py       # Demucs AI model wrapper
│   ├── module_spleeter.py     # Spleeter AI model wrapper
│   ├── module_ffmpeg.py       # FFmpeg utilities
│   ├── module_audio.py        # Audio alignment & mixing
│   ├── module_cuda.py         # GPU detection
│   └── module_ytdlp.py        # YouTube downloading
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
│   │   └── NotificationBell.jsx # Notification system
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
- `POST /api/separate` - Upload file for separation
- `POST /api/separate-file` - Separate existing file
- `POST /api/folder/scan` - Scan folder for batch processing
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
- `GET /api/presets` - Get quality presets
- `POST /api/presets` - Set current preset
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

| File Type | Duration | GPU (RTX 3060) | CPU (i7-12700K) |
|-----------|----------|----------------|-----------------|
| Music Video | 3:30 | 45 seconds | 4 minutes |
| Full Song | 5:00 | 1 minute | 6 minutes |
| Long Mix | 30:00 | 6 minutes | 35 minutes |
| Podcast | 60:00 | 12 minutes | 70 minutes |

*Times include both Spleeter + Demucs processing with alignment*

---

## 📝 Changelog

See [changelog.md](changelog.md) for detailed version history.

### v0.0.2 (2026-03-01)
- ✅ Queue system for downloads
- ✅ Batch folder processing
- ✅ In-app notifications
- ✅ Auto-retry failed downloads
- ✅ Auto-cleanup temp files
- ✅ Quality presets
- ✅ Library search & bulk delete

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

_Environment: Python 3.10+ (UV) + Deno 2.5 + Vite/React 18_
