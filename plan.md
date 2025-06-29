This Python script automates the process of isolating vocals from a video's audio track and then creating a new video with only those vocals, effectively removing background music. It achieves this by leveraging two powerful audio source separation tools, Spleeter and Demucs, and uses FFmpeg for all audio/video manipulation.

A key design choice in this specific version of the script is the **extensive use of temporary files and directories** for all intermediate steps. This ensures that your working directory remains clean, as all temporary data is automatically removed once the processing is complete.

---

## Python Script for Vocal Extraction and Video Re-Muxing

### Overview

This script takes an MP4 video file as input, extracts its audio, processes that audio using both Spleeter and Demucs to isolate the vocal track, combines these two vocal tracks, and then creates a new MP4 video file with the original video stream and the newly combined vocal-only audio.

### Features

*   **Audio Extraction:** Extracts audio from input video using FFmpeg.
*   **Dual Source Separation:** Utilizes both Spleeter and Demucs (specifically `htdemucs` model) for vocal separation, potentially leading to better results by combining their outputs.
*   **Audio Mixing:** Combines the vocal tracks from Spleeter and Demucs using FFmpeg's `amix` filter.
*   **Video Re-Muxing:** Creates a new video by combining the original video stream with the isolated and mixed vocal audio.
*   **GPU/CUDA Support Check:** Automatically detects and reports PyTorch CUDA availability, indicating if Demucs/Spleeter can leverage NVIDIA GPUs for faster processing.
*   **Automatic Cleanup:** All intermediate audio files and separation output directories are created as temporary files/directories and are automatically deleted upon script completion, regardless of success or failure.
*   **Error Handling:** Includes `try-except` blocks and `subprocess.run(check=True)` to catch and report errors during subprocess execution.

### How to run

Before running this script, you need to have the following installed:

1.  **UV**
    *   Run in PowerShell: powershell -c "irm https://astral.sh/uv/install.ps1 | more"
    
    *   After that run these commands
    *   `uv venv --python 3.10.0`
    *   `.venv\scripts\activate`
    *   `uv pip install -r requirements-310.txt`
    *   `uv pip uinstall torch torchvision torchaudio`

2. **CUDA Toolkit**
    * Download https://developer.nvidia.com/cuda-12-8-0-download-archive

5.  **PyTorch (Optional, but Recommended for GPU):**
    *   For GPU support (highly recommended for performance with Demucs/Spleeter), install PyTorch with CUDA. Replace `cu118` with your CUDA version.
    *   `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128`
    *   If you don't have an NVIDIA GPU or don't need GPU support, you can omit PyTorch installation, but the script will run on CPU, which is significantly slower.

