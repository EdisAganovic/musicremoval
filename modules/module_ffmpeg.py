"""
MODULE: module_ffmpeg.py - FFmpeg/FFprobe WRAPPER

ROLE: Manages FFmpeg binary and provides audio/video inspection utilities

RESPONSIBILITIES:
  - Auto-downloads ffmpeg.exe and ffprobe.exe to modules/ folder
  - Extracts audio tracks with language metadata
  - Gets audio duration and video resolution
  - Converts audio formats with optional normalization (loudnorm)

KEY FUNCTIONS:
  download_ffmpeg() → bool
    - Downloads FFmpeg if missing, returns True on success
  get_audio_tracks(input_file) → list[dict]
    - Returns [{index, language}, ...] for each audio stream
  get_audio_duration(file_path) → float | None
    - Returns duration in seconds
  get_video_resolution(file_path) → str | None
    - Returns "1920x1080" format
  convert_audio_with_ffmpeg(input, output, codec, normalize_audio) → bool
    - Converts audio, applies loudnorm if requested

CONSTANTS:
  FFMPEG_EXE: Absolute path to ffmpeg.exe in modules/
  FFPROBE_EXE: Absolute path to ffprobe.exe in modules/

DOWNLOAD SOURCE:
  - ffmpeg.exe: https://oblak.pronameserver.xyz/public.php/dav/files/8mW9BJCqLXX5ecp/?accept=zip
  - ffprobe.exe: https://oblak.pronameserver.xyz/public.php/dav/files/mGjWEPpJgC7xfiz/?accept=zip
"""
import subprocess
import json
from colorama import Fore, Style, Back
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from module_file import download_file_concurrent

def get_audio_tracks(input_file):
    """
    Retrieves audio tracks from a video file using ffprobe.
    """
    if not FFMPEG_EXE:
        print(f"{Fore.RED}FFmpeg not found. Cannot retrieve audio tracks.{Style.RESET_ALL}")
        return []

    ffprobe_exe = FFMPEG_EXE.replace('ffmpeg', 'ffprobe')
    command = [
        ffprobe_exe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a",
        input_file
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        streams = json.loads(result.stdout).get('streams', [])
        audio_tracks = []
        for stream in streams:
            lang = stream.get('tags', {}).get('language', 'unknown')
            audio_tracks.append({'index': stream['index'], 'language': lang})
        return audio_tracks
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{Fore.RED}Error getting audio tracks: {e}{Style.RESET_ALL}")
        return []
    except json.JSONDecodeError:
        print(f"{Fore.RED}Error parsing ffprobe output.{Style.RESET_ALL}")
        return []


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
            print(f"- Found '{file_info['filename']}' at: {os.path.abspath(local_filepath)}")
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
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
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
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get resolution for {file_path}. Error: {e}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting video resolution for {file_path}: {e}{Style.RESET_ALL}")
        return None

def get_file_metadata(file_path):
    """
    Gets resolution, duration, video codec, and audio codec using ffprobe.
    """
    metadata = {
        "resolution": "N/A",
        "duration": "N/A",
        "video_codec": "N/A",
        "audio_codec": "N/A",
        "is_video": False
    }
    
    try:
        cmd = [
            FFPROBE_EXE, 
            "-v", "quiet", 
            "-print_format", "json", 
            "-show_streams", 
            "-show_format", 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        data = json.loads(result.stdout)
        
        # Get duration
        format_info = data.get('format', {})
        duration = format_info.get('duration')
        if duration:
            try:
                metadata["duration"] = f"{float(duration):.2f}s"
            except:
                pass
        
        streams = data.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'video':
                metadata["is_video"] = True
                metadata["video_codec"] = stream.get('codec_name', 'N/A')
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    metadata["resolution"] = f"{width}x{height}"
            elif stream.get('codec_type') == 'audio':
                metadata["audio_codec"] = stream.get('codec_name', 'N/A')
                
        return metadata
    except Exception as e:
        print(f"Error getting metadata for {file_path}: {e}")
        return metadata

def get_video_codec(file_path):
    """
    Gets the video codec of a video file using ffprobe.
    Returns codec name as a string (e.g., "h264"), or None if an error occurs.
    """
    try:
        cmd = [FFPROBE_EXE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get video codec for {file_path}. Error: {e}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting video codec for {file_path}: {e}{Style.RESET_ALL}")
        return None

def check_fdk_aac_codec():
    """
    Checks if libfdk_aac codec is available in FFmpeg.
    """
    try:
        cmd = [FFMPEG_EXE, "-encoders"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
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

def convert_audio_with_ffmpeg(input_path, output_path, codec=None, normalize_audio=False):
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
        ]
        
        if normalize_audio:
            # Add loudnorm audio normalization filter
            cmd.extend(["-af", "loudnorm=I=-23:TP=-2:LRA=7"])
            print(f"{Fore.CYAN}Applying loudnorm audio normalization with I=-23:TP=-2:LRA=7{Style.RESET_ALL}")
        
        cmd.append(output_path)
        
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