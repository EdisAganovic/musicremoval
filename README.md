
This Python script automates the process of isolating vocals from a video's audio track and then creating a new video with only those vocals, effectively removing background music. It achieves this by leveraging two powerful audio source separation tools, Spleeter and Demucs, and uses FFmpeg for all audio/video manipulation.

A key design choice in this specific version of the script is the **extensive use of temporary files and directories** (managed via Python's `tempfile` module) for all intermediate steps. This ensures that your working directory remains clean, as all temporary data is automatically removed once the processing is complete, regardless of success or failure.

The script also utilizes `colorama` for enhanced terminal output, providing clearer visual feedback on different stages, warnings, and potential issues.

---

## Python Script for Vocal Extraction and Video Re-Muxing

### Overview

This script takes an MP4 video file (e.g., `patrol.mp4` as defined in `separate.py`) as input, extracts its audio, processes that audio using both Spleeter and Demucs to isolate the vocal track, intelligently combines these two vocal tracks, and then creates a new MP4 video file with the original video stream and the newly combined vocal-only audio.

### Features

*   **Audio Extraction:** Extracts audio from input video using FFmpeg.
*   **Dual Source Separation:** Utilizes both Spleeter and Demucs (specifically `htdemucs` model) for vocal separation, potentially leading to better results by combining their outputs.
*   **Intelligent Audio Alignment:** Before mixing, the script automatically aligns the Spleeter and Demucs vocal tracks using cross-correlation (`numpy`, `scipy`, `soundfile`). This compensates for any minor timing discrepancies introduced by the separation processes, ensuring precise synchronization.
*   **Spleeter Segmentation for Long Videos:** Automatically detects if the audio duration exceeds Spleeter's typical 10-minute (600 seconds) processing limit. If so, it splits the audio into segments, processes each segment with Spleeter, and then concatenates the resulting vocal tracks back together. This bypasses Spleeter's limitations with very long files.
*   **Audio Mixing:** Combines the aligned vocal tracks from Spleeter and Demucs using FFmpeg's `amix` filter, resulting in a single, high-quality vocal-only audio track.
    *   If only one vocal track (Spleeter or Demucs) is successfully generated, the script will automatically use that single track.
*   **Video Re-Muxing:** Creates a new video by combining the original video stream (copied without re-encoding) with the isolated and mixed vocal audio (encoded to AAC).
*   **GPU/CUDA Support Check:** Automatically detects and reports PyTorch CUDA availability, indicating if Demucs/Spleeter can leverage NVIDIA GPUs for faster processing. Provides helpful warnings and tips if CUDA is not found or configured.
*   **Automatic Cleanup:** All intermediate audio files (e.g., extracted WAV, split segments, aligned vocals) and separation output directories (`spleeter_out`, `demucs_out`) are created as temporary files/directories and are automatically deleted upon script completion, regardless of success or failure.
*   **Error Handling:** Includes robust `try-except` blocks and uses `subprocess.run(check=True)` to catch and report errors during subprocess execution (FFmpeg, Spleeter, Demucs commands). Enhanced readability is provided by `colorama` for distinct colored terminal output (e.g., green for success, red for errors, yellow for warnings).

### How to run

1.  **Python Environment with UV:**
    *   UV is recommended for managing Python environments and dependencies.
    *   **Install UV (if not already installed):**
        ```powershell
        powershell -c 'irm https://astral.sh/uv/install.ps1 | iex' # On Windows PowerShell
        # curl -LsSf https://astral.sh/uv/install.sh | sh # On Linux/macOS
        ```
    *   **Create and Activate Virtual Environment:**
        ```bash
        uv venv --python 3.10.0 # Creates a virtual environment with Python 3.10
        .venv\scripts\activate  # On Windows PowerShell/CMD
        # source .venv/bin/activate # On Linux/macOS or Git Bash
        ```
    *   **Install Base Python Dependencies:**
        ```bash
        uv pip install -r requirements.txt
        ```
        *This will install `spleeter`, `demucs`, `colorama`, `pydub`, `numpy`, `scipy`, `soundfile`, and a CPU-only version of `torch` by default.*

2.  **PyTorch with GPU Support (Optional, but Highly Recommended for Performance):**
    *   If you have an NVIDIA GPU, this step ensures Demucs and Spleeter utilize it.
    *   Download https://developer.nvidia.com/cuda-12-8-0-download-archive and install it.
    *   **First, uninstall the CPU version of PyTorch installed by `requirements.txt`:**

        `uv pip uninstall torch torchvision torchaudio`

    *   **Then, install the GPU version (replace `cu128` with your specific CUDA version, e.g., `cu124`, `cu118` based on your CUDA Toolkit installation):**
        ```bash
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
        ```
        *(Ensure the CUDA version in the `--index-url` matches your installed NVIDIA CUDA Toolkit version. Refer to [PyTorch's official installation page](https://pytorch.org/get-started/locally/) for the correct `index-url` based on your CUDA version and OS).*
    *   If you don't have an NVIDIA GPU or choose not to use GPU support, you can omit this step (the `uv pip install -r requirements.txt` will provide a CPU-only version of PyTorch), but the script will run on CPU, which is significantly slower for separation tasks.

### Usage

1.  **Place your video file** in the same directory as `main.py`.
2.  **Activate virtual enviroment** in terminal
    ```bash
    .venv\scripts\Activate\
    ```
3.  **Download file with integrated YT-DLP**
    ```bash
    python main.py download URL FILENAME
    ```
    URL = https://youtu.be/example
    FILENAME = Cartoon.mp4
2.  **Run the script**
    ```bash
    python main.py separate video.mp4
    ```

The script will provide detailed, colored output showing each step of the process. Upon completion, a new video file named `nomusic-<original_filename>` (e.g., `nomusic-patrol.mp4`) will be created in the same directory, containing only the isolated vocal tracks.