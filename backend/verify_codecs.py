import subprocess
import os

def tracked_run(command, **kwargs):
    return subprocess.run(command, **kwargs)

FFMPEG_EXE = r"c:\Users\Ensarija\Desktop\PYTHON_PROJEKTI_2025\demucspleeter\backend\modules\ffmpeg.exe"

def get_video_codec(file_path):
    if not os.path.exists(FFMPEG_EXE.replace('ffmpeg', 'ffprobe')):
        return f"ffprobe not found at {FFMPEG_EXE.replace('ffmpeg', 'ffprobe')}"

    ffprobe_exe = FFMPEG_EXE.replace('ffmpeg', 'ffprobe')
    command = [
        ffprobe_exe,
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    
    try:
        result = tracked_run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        return result.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"error: {str(e)}"

# Test with a known file if possible, or just print path
print(f"Testing codec detection...")
# Note: I don't have a guaranteed video file path here, but I can check if ffprobe exists
print(f"FFprobe path: {FFMPEG_EXE.replace('ffmpeg', 'ffprobe')}")
print(f"Exists: {os.path.exists(FFMPEG_EXE.replace('ffmpeg', 'ffprobe'))}")
