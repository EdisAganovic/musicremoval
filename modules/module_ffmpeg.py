import subprocess
from colorama import Fore, Style, Back
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from module_file import download_file_concurrent

FFMPEG_EXE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ffmpeg.exe'))
FFPROBE_EXE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ffprobe.exe'))

def download_ffmpeg():
    """
    Downloads ffmpeg.exe and ffprobe.exe to the modules folder if they don't exist.
    """
    files_config = [
        {"url": "https://oblak.pronameserver.xyz/public.php/dav/files/8mW9BJCqLXX5ecp/?accept=zip", "filename": "ffmpeg.exe"},
        {"url": "https://oblak.pronameserver.xyz/public.php/dav/files/mGjWEPpJgC7xfiz/?accept=zip", "filename": "ffprobe.exe"}
    ]

    print(f"\n{Back.RED}{Fore.WHITE}# FFMPEG Download {Style.RESET_ALL}\n")
    
    # The target directory is the same as this script's directory
    target_dir = os.path.dirname(__file__)
    
    files_to_actually_download = []
    for file_info in files_config:
        # Prepend the target directory to the filename
        local_filepath = os.path.join(target_dir, file_info["filename"])
        if os.path.exists(local_filepath):
            print(f"- Skipping '{file_info['filename']}': File already exists locally.")
        else:
            # Pass the full path to the download function
            files_to_actually_download.append({
                "url": file_info["url"],
                "filename": local_filepath # Full path for download
            })
            print(f"- '{file_info['filename']}' does not exist locally, will attempt to download.")

    if not files_to_actually_download:
        print("\nNo new files to download. All specified files already exist locally.")
        return True
    
    print("\n--- Starting Concurrent Downloads ---")
    all_successful = True
    with ThreadPoolExecutor(max_workers=len(files_to_actually_download)) as executor:
        future_to_file = {executor.submit(download_file_concurrent, f["url"], f["filename"]): f for f in files_to_actually_download}

        for future in as_completed(future_to_file):
            original_file_info = future_to_file[future]
            success, filepath = future.result()
            
            # Get just the filename for printing
            filename_for_print = os.path.basename(filepath)

            if success:
                print(f"[{filename_for_print}] Download finished.")
            else:
                print(f"[{filename_for_print}] Download failed.")
                all_successful = False
    
    return all_successful

def get_audio_duration(file_path):
    """
    Gets the duration of an audio file using ffprobe.
    Returns duration in seconds as float, or None if an error occurs.
    """
    try:
        # Use ffprobe to get duration
        cmd = [FFPROBE_EXE, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
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
        cmd = [FFPROBE_EXE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get resolution for {file_path}. Error: {e}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting video resolution for {file_path}: {e}{Style.RESET_ALL}")
        return None

def check_fdk_aac_codec():
    """
    Checks if libfdk_aac codec is available in FFmpeg.
    """
    try:
        cmd = [FFMPEG_EXE, "-encoders"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if "libfdk_aac" in result.stdout:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: FFmpeg failed to list encoders. Is FFmpeg installed and in PATH? Error: {e}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while checking for libfdk_aac: {e}{Style.RESET_ALL}")
        return False

def convert_audio_with_ffmpeg(input_path, output_path, codec=None):
    """
    Converts audio using FFmpeg, preferring libfdk_aac if available.
    """
    if codec is None:
        if check_fdk_aac_codec():
            audio_codec = "libfdk_aac"
            print(f"{Fore.GREEN}Using libfdk_aac for audio encoding.{Style.RESET_ALL}")
        else:
            audio_codec = "aac"
            print(f"{Fore.YELLOW}libfdk_aac not found. Falling back to aac for audio encoding.{Style.RESET_ALL}")
    else:
        audio_codec = codec
        print(f"{Fore.CYAN}Using specified codec: {audio_codec} for audio encoding.{Style.RESET_ALL}")

    try:
        cmd = [
            FFMPEG_EXE,
            "-i", input_path,
            "-loglevel","error",
            "-y",
            "-c:a", audio_codec,
            "-b:a", "192k", # Example bitrate, adjust as needed
            output_path
        ]
        print(f"Executing FFmpeg command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print(f"{Fore.GREEN}Successfully converted {input_path} to {output_path} using {audio_codec}.{Style.RESET_ALL}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: FFmpeg failed to convert audio. Command: {' '.join(e.cmd)}. Error: {e.stderr}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during audio conversion: {e}{Style.RESET_ALL}")
        return False
