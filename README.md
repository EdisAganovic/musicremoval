# Demucs & Spleeter Vocal Extractor

This Python script provides a command-line interface to automate the process of isolating vocals from video or audio files. It uses **Demucs** and **Spleeter**, two powerful audio source separation tools, to get the best possible result. The script can process local files or download videos from the web, then creates a new video with only the isolated vocals, effectively removing background music and other noise.

A key design choice is the **extensive use of temporary files**, ensuring the working directory remains clean. All intermediate data is automatically removed upon completion. The script also features color-coded terminal output for better readability.

---

## Features

*   **Command-Line Interface:** A clean CLI for downloading videos and separating vocals.
*   **Dual Source Separation:** Utilizes both Spleeter and Demucs (`htdemucs` model) for vocal separation.
*   **Intelligent Audio Alignment:** Automatically aligns the Spleeter and Demucs vocal tracks using cross-correlation to compensate for any timing discrepancies before they are combined.
*   **Automatic Segmentation for Long Audio:** If the audio duration exceeds 10 minutes, the script automatically splits the audio into segments for both Spleeter and Demucs, processes each chunk, and then seamlessly concatenates the results. This bypasses the memory and processing limitations of the tools with very long files.
*   **Flexible Vocal Track Handling:**
    *   If both Spleeter and Demucs produce a vocal track, the script uses the aligned track from Spleeter.
    *   If only one of the tools succeeds, the script uses the single available vocal track.
*   **Video Downloading:** Includes a `download` command that uses `yt-dlp` to fetch videos from URLs, with fallback logic to find the best available format.
*   **Batch Processing:** The `separate` command can process a single file or all video files within a specified folder.
*   **Video Re-Muxing:** Creates a new video file by combining the original video stream with the new vocal-only audio track.
*   **Configurable Output:** Video and audio settings for the final output (codec, bitrate, format) can be customized via a `video.json` file.
*   **GPU/CUDA Support Check:** Automatically detects if a CUDA-enabled GPU is available for significantly faster processing and provides feedback.
*   **Automatic Dependencies:** Downloads FFmpeg/FFprobe automatically if they are not found in the `modules` directory.
*   **Automatic Cleanup:** All temporary files and directories (`spleeter_out`, `demucs_out`, temp wavs, etc.) are automatically deleted after processing.
*   **Robust Error Handling:** Provides clear error messages and warnings.

## How to run

1.  **Python Environment with UV:**
    *   This project uses `uv` for fast Python environment and package management.
    *   **Install UV (if not already installed):**
        ```powershell
        powershell -c 'irm https://astral.sh/uv/install.ps1 | iex'
        ```
        *For Linux/macOS, see the [official uv installation guide](https://github.com/astral-sh/uv#installation).*
    *   **Create and Activate Virtual Environment:**
        ```bash
        uv venv --python 3.10 # Creates a virtual environment
        .venv\scripts\activate  # On Windows
        # source .venv/bin/activate # On Linux/macOS
        ```
    *   **Install Dependencies:**
        ```bash
        uv pip install -r requirements.txt
        ```
        *This installs all necessary packages, including a CPU-only version of PyTorch.*

2.  **Download and install CUDA toolkit**

    * Download https://developer.nvidia.com/cuda-12-8-0-download-archive

3.  **PyTorch with GPU Support (Optional, but HIGHLY Recommended):**
    *   For a massive performance boost, install PyTorch with CUDA support if you have an NVIDIA GPU.
    *   Find your CUDA version by running `nvidia-smi`.
    *   **First, uninstall the CPU-only PyTorch:**
        ```bash
        uv pip uninstall torch torchvision torchaudio
        ```
    *   **Then, install the GPU version.** Replace `cu121` with your specific CUDA version (e.g., `cu118`).
        ```bash
        # Example for CUDA 12.1
        uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        ```
        *Refer to the [PyTorch official website](https://pytorch.org/get-started/locally/) for the correct command for your system.*

## Usage

The script is run from the command line and has two main commands: `download` and `separate`.

### 1. Download a Video

This command uses `yt-dlp` to download a video. The downloaded file will be saved in the `download/` folder.

**Syntax:**
```bash
python main.py download <URL> [FILENAME]
```

**Example:**
```bash
# Download a video and let yt-dlp decide the filename
python main.py download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download a video and save it as "MyVideo.mp4"
python main.py download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "MyVideo.mp4"
```

### 2. Separate Vocals

This command processes video files to remove music and leave only vocals. The final video is saved in the `nomusic/` directory.

**Process a single video file:**
```bash
python main.py separate --file "path/to/your/video.mp4"
```

**Process all videos in a folder:**
```bash
python main.py separate --folder "path/to/your/videos_folder"
```

---

## Configuration (`video.json`)

You can control the output video and audio quality by creating a `video.json` file in the root directory. If this file doesn't exist, the script will use default settings.

**Example `video.json`:**
```json
{
  "video": {
    "codec": "h264_nvenc", # GPU accelerated encoding
    "bitrate": 1800k  # perfect balance for FullHD res
  },
  "audio": {
    "codec": "lifdk_aac", # 4x speed improvement with this codec
    "bitrate": 128k
  },
  "output": {
    "format": "mp4"
  }
}
```

*   **`video.codec`**: The video codec for the output file. Use `"copy"` to stream copy the original video track without re-encoding (fastest and preserves quality). You can also specify a codec like `"libx264"`.
*   **`video.bitrate`**: Target video bitrate (e.g., `"4000k"`). Only used if `codec` is not `"copy"`.
*   **`audio.codec`**: The audio codec for the vocal track. Defaults to `"aac"`.
*   **`audio.bitrate`**: Target audio bitrate (e.g., `"192k"`, `"256k"`).
*   **`output.format`**: The container format for the final video (e.g., `"mp4"`, `"mkv"`).