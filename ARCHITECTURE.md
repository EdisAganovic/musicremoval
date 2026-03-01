# Architecture Overview

## Quick Reference

### Backend (Python)

| File | Purpose | Key Functions |
|------|---------|---------------|
| `main.py` | CLI entry point for download/separate commands | `main()` |
| `tools.py` | Utility CLI for inspecting audio tracks | `main()` |
| `modules/module_processor.py` | Main orchestrator for vocal separation | `process_file()`, `load_config()` |
| `modules/module_demucs.py` | Demucs AI model wrapper with segmentation | `separate_with_demucs()` |
| `modules/module_spleeter.py` | Spleeter AI model wrapper with segmentation | `separate_with_spleeter()` |
| `modules/module_ffmpeg.py` | FFmpeg/FFprobe wrapper for audio extraction & conversion | `download_ffmpeg()`, `get_audio_tracks()`, `get_audio_duration()`, `convert_audio_with_ffmpeg()` |
| `modules/module_ytdlp.py` | YouTube video downloader | `download_video()`, `check_and_update_ytdlp()` |
| `modules/module_audio.py` | Audio alignment (cross-correlation) and mixing | `align_audio_tracks()`, `mix_audio_tracks()`, `calculate_audio_lag()` |
| `modules/module_cuda.py` | GPU/CUDA detection | `check_gpu_cuda_support()` |
| `modules/module_deno.py` | Deno runtime helper for JS/TS scripts | `run_deno_script()`, `deno_eval()` |
| `modules/module_file.py` | File utilities and concurrent downloads | `download_file_concurrent()`, `calculate_file_hash()` |

### Frontend (React)

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| `App.jsx` | Root component with tab navigation | Tab switching, layout, status footer |
| `SeparationTab.jsx` | File upload & vocal separation UI | Drag-drop, batch processing, progress polling |
| `DownloaderTab.jsx` | YouTube downloader | Format selection, queue system, subtitles |
| `LibraryTab.jsx` | Processed files browser | Search, sort, bulk delete, re-separate |
| `NotificationBell.jsx` | Notification dropdown | Unread count, mark read, clear all |
| `NotificationContext.jsx` | Notification state management | Auto-polling, optimistic updates |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                      │
│    CLI: main.py separate --file OR web UI upload                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  module_processor.process_file()  ← ORCHESTRATOR                       │
│    1. Validate input file                                               │
│    2. Check GPU (module_cuda)                                           │
│    3. Get audio tracks (module_ffmpeg)                                  │
│    4. Extract audio to WAV                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────────┐       ┌───────────────────────┐
        │  module_spleeter      │       │  module_demucs        │
        │  - Split >10min       │       │  - Split >10min       │
        │  - 2stems model       │       │  - htdemucs model     │
        │  - Parallel workers   │       │  - Parallel workers   │
        └───────────────────────┘       └───────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  module_audio.align_audio_tracks()                                      │
│    - Cross-correlation to detect lag                                    │
│    - Pad earlier track to sync                                          │
│    - Mix both tracks (0.5 + 0.5)                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  module_ffmpeg.convert_audio_with_ffmpeg()                              │
│    - Apply loudnorm normalization                                       │
│    - Convert to output format (AAC/MP3/FLAC)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: ./nomusic/ folder + update video.json                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Dependencies

```
main.py
  ├── module_ffmpeg (download_ffmpeg, get_audio_tracks)
  ├── module_ytdlp (download_video)
  └── module_processor (process_file)
        ├── module_cuda (check_gpu_cuda_support)
        ├── module_ffmpeg (get_audio_duration, convert_audio_with_ffmpeg)
        ├── module_spleeter (separate_with_spleeter)
        ├── module_demucs (separate_with_demucs)
        └── module_audio (align_audio_tracks, mix_audio_tracks)

module_spleeter
  └── module_ffmpeg (get_audio_duration, FFMPEG_EXE)

module_demucs
  └── module_ffmpeg (get_audio_duration, FFMPEG_EXE)

module_ytdlp
  └── module_ffmpeg (get_video_resolution)

module_audio
  └── module_ffmpeg (get_audio_duration, FFMPEG_EXE)
```

## Key JSON Files

| File | Purpose | Updated By |
|------|---------|------------|
| `video.json` | Library database + quality presets | module_processor, web UI |
| `download_queue.json` | YouTube download queue state | web UI |
| `notifications.json` | User notification history | web UI |
| `library.json` | Processed files metadata | web UI |

## Configuration (video.json)

```json
{
  "presets": {
    "fast": { ... },      // Copy video, 128k audio
    "balanced": { ... },  // h264_nvenc, 192k audio (default)
    "quality": { ... }    // hevc_nvenc, 256k audio
  },
  "video": { "codec": "...", "bitrate": "..." },
  "audio": { "codec": "...", "bitrate": "..." },
  "output": { "format": "mp4" },
  "processing": { "demucs_workers": 2 }
}
```

## Temporary Files

| Path | Purpose | Cleaned |
|------|---------|---------|
| `_temp/` | General temp files | On success (unless --temp) |
| `spleeter_out/` | Spleeter intermediate output | Manual |
| `demucs_out/` | Demucs intermediate output | Manual |
| `downloads/` | YouTube downloads | Manual |
| `nomusic/` | Final output | Never (user data) |

## Processing Pipeline Steps

1. **Input Validation** - Check file exists, get audio tracks
2. **GPU Check** - Detect CUDA availability
3. **Audio Extraction** - Extract to WAV with FFmpeg (stereo downmix)
4. **AI Separation** - Run Spleeter and Demucs (parallel if >10min)
5. **Alignment** - Cross-correlation to fix millisecond offsets
6. **Mixing** - Combine both model outputs (equal weight)
7. **Sync Correction** - Detect and pad any remaining lag
8. **Normalization** - Apply loudnorm (EBU R128)
9. **Final Encode** - Convert to output format with video (if applicable)
10. **Cleanup** - Remove temp files (unless --temp flag)

## Error Handling Strategy

- **Model Failure**: If Spleeter OR Demucs fails, continue with the other
- **Alignment Failure**: Fall back to unaligned mix
- **FFmpeg Failure**: Return False, abort processing
- **GPU Unavailable**: Fall back to CPU (slower but functional)

## Performance Notes

- **Segmentation**: Files >10min split into 600s chunks
- **Parallel Workers**: Demucs uses `demucs_workers` from config (default: 2)
- **Memory**: Demucs uses ~8GB RAM per concurrent worker
- **GPU**: 5-10x faster than CPU for AI models

---

## Frontend Architecture

### Component Hierarchy

```
App.jsx (Root)
├── NotificationProvider (Context)
│   └── NotificationBell (Header)
├── Header (Logo, Title)
├── Tab Navigation (Pill-style)
│   ├── Separation Tab
│   ├── Downloader Tab
│   └── Library Tab
└── Footer (Status indicators)
```

### State Management

| State | Location | Purpose |
|-------|----------|---------|
| `activeTab` | App.jsx | Current tab selection |
| `notifications` | NotificationContext | Global notification state |
| `file`, `status`, `progress` | SeparationTab | Upload/processing state |
| `url`, `queue`, `videoInfo` | DownloaderTab | Download state |
| `items`, `selectedItems` | LibraryTab | Library items + selection |

### Polling Intervals

| Feature | Interval | Purpose |
|---------|----------|---------|
| Task progress | 1000ms | Real-time separation progress |
| Batch progress | 2000ms | Batch processing updates |
| Queue status | 2000ms | Download queue updates |
| Notifications | 3000ms | New notification checks |
| Library refresh | 10000ms | Auto-refresh completed files |

### Design System

- **Framework**: React 18 + Vite
- **Animations**: framer-motion (layout transitions, hover effects)
- **Icons**: lucide-react
- **Styling**: Tailwind CSS with custom glassmorphism
- **Colors**: Dark theme with primary (blue/purple) and accent (emerald) gradients
- **Effects**: Backdrop blur, gradient borders, shadow layers

### API Communication Pattern

```javascript
// 1. Trigger action
const handleUpload = async () => {
  // 2. Start processing state
  setStatus("processing");
  
  // 3. Call API
  const response = await axios.post("/api/separate", formData);
  setTaskId(response.data.task_id);
  
  // 4. Poll for progress (useEffect)
  useEffect(() => {
    const interval = setInterval(async () => {
      const status = await axios.get(`/api/status/${taskId}`);
      setProgress(status.data.progress);
      if (status.data.status === "completed") {
        clearInterval(interval);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [taskId]);
};
```

### Key UI Features

**Separation Tab:**
- Drag & drop with visual feedback
- Mode switch (Single File / Process Folder)
- File selection checkboxes for batch
- Progress bar with current step
- Result cards with action buttons

**Downloader Tab:**
- URL analysis with thumbnail preview
- Format filtering (audio/video)
- Subtitle language selection
- Queue panel with management controls
- Download cancellation

**Library Tab:**
- Search and sort controls
- Multi-select with bulk operations
- File metadata display
- Quick actions (play, separate, open folder)
