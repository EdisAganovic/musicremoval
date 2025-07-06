import subprocess
from colorama import Fore, Style

def get_audio_duration(file_path):
    """
    Gets the duration of an audio file using ffprobe.
    Returns duration in seconds as float, or None if an error occurs.
    """
    try:
        # Use ffprobe to get duration
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get duration for {file_path}. Is ffprobe installed and in PATH? Error: {e}{Style.RESET_ALL}")
        return None
    except ValueError:
        print(f"{Fore.RED}Error: ffprobe returned non-numeric duration for {file_path}.{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting audio duration for {file_path}: {e}{Style.RESET_ALL}")
        return None

def get_video_resolution(file_path):
    """
    Gets the resolution of a video file using ffprobe.
    Returns resolution as a string (e.g., "1920x1080"), or None if an error occurs.
    """
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get resolution for {file_path}. Error: {e}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting video resolution for {file_path}: {e}{Style.RESET_ALL}")
        return None
