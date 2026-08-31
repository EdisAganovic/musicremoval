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
import tempfile
from colorama import Fore, Style, Back
import os
import sys
import shutil
try:
    from module_file import download_file_concurrent
except ImportError:
    from modules.module_file import download_file_concurrent

try:
    from services.process_manager import tracked_run
except ImportError:
    tracked_run = subprocess.run

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
        result = tracked_run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        streams = json.loads(result.stdout).get('streams', [])
        audio_tracks = []
        for stream in streams:
            lang = stream.get('tags', {}).get('language', 'unknown')
            audio_tracks.append({'index': stream['index'], 'language': lang})
        return audio_tracks
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{Fore.RED}Error getting audio tracks: {e}{Style.RESET_ALL}")
        return []
def get_video_codec(file_path):
    """
    Retrieves the video codec name from a file using ffprobe.
    """
    if not FFMPEG_EXE:
        return "unknown"

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
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


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
        result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
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

def split_audio_into_segments(temp_audio_wav_path, audio_duration, segment_duration_seconds, temp_dir_parent="_temp"):
    """
    Splits a WAV file into sequential segments of `segment_duration_seconds` using ffmpeg.
    Shared by module_demucs.py and module_spleeter.py, which both need to chop long
    audio into chunks before parallel/sequential model processing.

    Args:
        temp_audio_wav_path: Path to the source WAV file.
        audio_duration: Total duration of the source file in seconds (from get_audio_duration).
        segment_duration_seconds: Max length of each segment.
        temp_dir_parent: Parent directory the segments temp dir is created under.

    Returns:
        tuple: (segments_dir, [segment_path, ...]) in chronological order.
    """
    os.makedirs(temp_dir_parent, exist_ok=True)
    segments_dir = tempfile.mkdtemp(dir=temp_dir_parent)
    segment_paths = []

    current_start_time = 0
    segment_index = 0

    while current_start_time < audio_duration:
        segment_duration = min(segment_duration_seconds, audio_duration - current_start_time)
        segment_filename = f"part_{segment_index:03d}.wav"
        segment_output_path = os.path.join(segments_dir, segment_filename)

        ffmpeg_split_cmd = [
            FFMPEG_EXE, "-y",
            "-loglevel", "error",
            "-i", temp_audio_wav_path,
            "-ss", str(current_start_time),
            "-t", str(segment_duration),
            segment_output_path
        ]
        print(f"- Splitting audio: {segment_filename} from {current_start_time:.2f}s for {segment_duration:.2f}s...")
        tracked_run(ffmpeg_split_cmd, check=True)
        segment_paths.append(segment_output_path)

        current_start_time += segment_duration
        segment_index += 1

    return segments_dir, segment_paths


def get_video_resolution(file_path):
    """
    Gets the resolution of a video file using ffprobe.
    Returns resolution as a string (e.g., "1920x1080"), or None if an error occurs.
    """
    try:
        cmd = [FFPROBE_EXE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path]
        result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
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
        try:
            result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if result.returncode != 0:
                print(f"ffprobe failed for {file_path}. Return code: {result.returncode}, stderr: {result.stderr}")
                return metadata
            data = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            print(f"ffprobe timed out (10s) for {file_path}")
            return metadata
        except json.JSONDecodeError:
            print(f"Failed to parse ffprobe JSON output for {file_path}")
            return metadata

        # Get duration - try format first, then fall back to video stream
        format_info = data.get('format', {})
        duration = format_info.get('duration')

        streams = data.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'video':
                metadata["is_video"] = True
                metadata["video_codec"] = stream.get('codec_name', 'N/A')
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    metadata["resolution"] = f"{width}x{height}"

                # Fall back to video stream duration if not in format
                if not duration:
                    duration = stream.get('duration')
                    # Also try duration_ts with time_base
                    if not duration and stream.get('duration_ts') and stream.get('time_base'):
                        try:
                            duration = float(stream['duration_ts']) * float(stream['time_base'])
                        except (ValueError, TypeError):
                            pass

            elif stream.get('codec_type') == 'audio':
                metadata["audio_codec"] = stream.get('codec_name', 'N/A')

        if duration:
            try:
                duration_seconds = float(duration)
                # Format as HH:MM:SS for better readability
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                seconds = int(duration_seconds % 60)
                if hours > 0:
                    metadata["duration"] = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    metadata["duration"] = f"{minutes}:{seconds:02d}"
            except (ValueError, TypeError):
                pass

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
        result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get video codec for {file_path}. Error: {e}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting video codec for {file_path}: {e}{Style.RESET_ALL}")
        return None

def get_ffmpeg_version():
    """
    Retrieves a clean version string (e.g., "8.0.1") from the local FFmpeg binary.
    """
    if not os.path.exists(FFMPEG_EXE):
        return "N/A"
    
    try:
        # Run ffmpeg -version
        result = tracked_run([FFMPEG_EXE, "-version"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        # First line usually looks like: "ffmpeg version 8.0.1-full_build-www.gyan.dev Copyright..."
        first_line = result.stdout.split('\n')[0]
        
        # Look for "version " and take the next part
        if "version " in first_line:
            version_part = first_line.split("version ")[1].split(" ")[0]
            # Strip extra build info if present (e.g. "-full_build...")
            clean_version = version_part.split("-")[0]
            # Strip leading 'n' if present (e.g. "n5.1.2" -> "5.1.2")
            if clean_version.startswith('n'):
                clean_version = clean_version[1:]
            return clean_version
            
        return "Available"
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return "N/A"

def check_fdk_aac_codec():
    """
    Checks if libfdk_aac codec is available in FFmpeg.
    """
    try:
        cmd = [FFMPEG_EXE, "-encoders"]
        result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
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
        tracked_run(cmd, check=True)
        print(f"{Fore.GREEN}Successfully converted {input_path} to {output_path} using {audio_codec}.{Style.RESET_ALL}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: FFmpeg failed to convert audio. Command: {' '.join(e.cmd)}. Error: {e.stderr}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during audio conversion: {e}{Style.RESET_ALL}")
        return False

_NVENC_H264_AVAILABLE = None

def check_nvenc_h264_support():
    """
    Checks if h264_nvenc encoder is available and functioning with FFmpeg.
    Caches the result to avoid repeating test encodes.
    """
    global _NVENC_H264_AVAILABLE
    if _NVENC_H264_AVAILABLE is not None:
        return _NVENC_H264_AVAILABLE

    if not FFMPEG_EXE or not os.path.exists(FFMPEG_EXE):
        _NVENC_H264_AVAILABLE = False
        return False

    try:
        cmd = [FFMPEG_EXE, "-encoders"]
        result = tracked_run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        if "h264_nvenc" not in result.stdout:
            _NVENC_H264_AVAILABLE = False
            return False

        # Quick test encode to ensure NVIDIA driver / hardware initializes correctly
        # Minimum resolution for NVENC on newer architectures is >= 128x128 (64x64 fails)
        test_cmd = [
            FFMPEG_EXE, "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.04",
            "-frames:v", "1",
            "-c:v", "h264_nvenc",
            "-f", "null", "-"
        ]
        test_run = tracked_run(test_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        _NVENC_H264_AVAILABLE = (test_run.returncode == 0)
    except Exception as e:
        print(f"{Fore.YELLOW}Note: NVENC H.264 probe returned: {e}{Style.RESET_ALL}")
        _NVENC_H264_AVAILABLE = False

    return _NVENC_H264_AVAILABLE

def resolve_h264_video_codec(requested_codec="h264_nvenc"):
    """
    Resolves the best available H.264 video codec.
    - If requested is 'copy', returns 'copy'.
    - If requested is 'h264_nvenc', checks GPU/NVENC support; falls back to 'libx264' if unavailable.
    - Explicitly rejects x265/HEVC and redirects to H.264.
    - Defaults to 'libx264' for general H.264 requests.
    """
    if not requested_codec or requested_codec == "copy":
        return "copy"

    req = str(requested_codec).strip().lower()

    # Disallow x265 / hevc
    if req in ["x265", "h265", "hevc", "hevc_nvenc", "libx265"]:
        print(f"{Fore.YELLOW}x265/HEVC is disabled. Redirecting to H.264 pipeline.{Style.RESET_ALL}")
        req = "h264_nvenc"

    if req == "h264_nvenc":
        if check_nvenc_h264_support():
            print(f"{Fore.GREEN}Using hardware accelerated H.264 (h264_nvenc).{Style.RESET_ALL}")
            return "h264_nvenc"
        else:
            print(f"{Fore.YELLOW}h264_nvenc not supported by GPU/driver. Falling back to libx264 (CPU).{Style.RESET_ALL}")
            return "libx264"
    elif req in ["h264", "x264", "libx264"]:
        return "libx264"

    return req


def find_closest_keyframe(file_path, target_time_seconds, min_margin=5.0):
    """
    Finds the keyframe (I-frame) timestamp in a video file closest to target_time_seconds.
    Uses fast FFmpeg keyframe probe; defaults to target_time_seconds on timeout or error.
    """
    if not FFMPEG_EXE or not os.path.exists(FFMPEG_EXE):
        return target_time_seconds

    try:
        # Fast probe using showinfo seeking right at target
        probe_cmd = [
            FFMPEG_EXE, "-ss", str(max(0, target_time_seconds - 5)),
            "-i", file_path,
            "-frames:v", "1",
            "-vf", "showinfo",
            "-f", "null", "-"
        ]
        result = tracked_run(probe_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        # If fast probe returns, return target_time_seconds
        return target_time_seconds
    except Exception:
        return target_time_seconds


def get_resolution_scale_filter(resolution: str = "1080p") -> str:
    """
    Returns the appropriate FFmpeg scale filter based on resolution selection.
    """
    res = (resolution or "1080p").lower()
    if res in ["720p", "720"]:
        return "scale='min(1280,iw)':-2,format=yuv420p"
    elif res in ["480p", "480"]:
        return "scale='min(854,iw)':-2,format=yuv420p"
    elif res in ["4k", "2160p", "2160"]:
        return "scale='min(3840,iw)':-2,format=yuv420p"
    elif res in ["original", "source"]:
        return "format=yuv420p"
    else:  # default 1080p
        return "scale='min(1920,iw)':-2,format=yuv420p"


def execute_super_keyframe_nvenc_export(
    input_file, audio_file, output_file, output_format,
    video_bitrate, audio_codec, audio_bitrate,
    num_chunks=None,
    resolution="1080p",
    update_progress_cb=None
):
    """
    Executes 'Super Keyframe' parallel multi-chunk NVENC video encoding.
    Splits video and audio into parallel chunks matching the user's NVIDIA card capability,
    runs hardware-accelerated NVENC instances across GPU NVENC engines in parallel, and joins them using concat demuxer.
    """
    from concurrent.futures import ThreadPoolExecutor
    from module_cuda import get_optimal_nvenc_chunks

    duration = get_audio_duration(input_file)
    if not duration or duration < 30.0:
        print(f"{Fore.YELLOW}Video duration ({duration}s) too short for Super Keyframe parallel chunking. Using standard export.{Style.RESET_ALL}")
        return False

    gpu_optimal = get_optimal_nvenc_chunks(default=4)
    target_chunks = num_chunks if num_chunks is not None else gpu_optimal
    actual_chunks = target_chunks if duration >= 60.0 else 2
    chunk_len = duration / actual_chunks

    print(f"\n{Fore.CYAN}[Super Keyframe] Splitting video into {actual_chunks} parallel chunks (~{chunk_len:.2f}s each, Total: {duration:.2f}s, Resolution: {resolution}) for {actual_chunks}x NVENC encoding...{Style.RESET_ALL}")

    temp_chunk_dir = tempfile.mkdtemp(dir="_temp", prefix="super_kf_")
    concat_list_path = os.path.join(temp_chunk_dir, "concat_list.txt")
    chunk_paths = [os.path.join(temp_chunk_dir, f"part_{i:03d}.mp4") for i in range(actual_chunks)]

    try:
        def build_chunk_cmd(start_time, duration_limit, out_path):
            cmd = [
                FFMPEG_EXE, "-loglevel", "error", "-y",
                "-hwaccel", "cuda",
            ]
            if start_time is not None:
                cmd.extend(["-ss", f"{start_time:.3f}"])
            if duration_limit is not None:
                cmd.extend(["-t", f"{duration_limit:.3f}"])
            cmd.extend(["-i", input_file])

            if start_time is not None:
                cmd.extend(["-ss", f"{start_time:.3f}"])
            if duration_limit is not None:
                cmd.extend(["-t", f"{duration_limit:.3f}"])
            cmd.extend(["-i", audio_file])

            scale_filter = get_resolution_scale_filter(resolution)
            cmd.extend([
                "-vf", scale_filter,
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-tune", "hq"
            ])
            if video_bitrate:
                cmd.extend(["-b:v", video_bitrate])

            cmd.extend(["-c:a", audio_codec if audio_codec else "aac"])
            if audio_bitrate:
                cmd.extend(["-b:a", audio_bitrate])

            cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-shortest", "-f", "mp4", out_path])
            return cmd

        # Build commands for all chunks
        chunk_cmds = []
        for i in range(actual_chunks):
            start_t = None if i == 0 else i * chunk_len
            dur_t = chunk_len if i < (actual_chunks - 1) else None
            chunk_cmds.append((i, build_chunk_cmd(start_t, dur_t, chunk_paths[i])))

        def run_encode(chunk_idx, cmd):
            print(f"{Fore.MAGENTA}[Super Keyframe] Launching NVENC Chunk {chunk_idx + 1}/{actual_chunks}: {' '.join(cmd)}{Style.RESET_ALL}")
            tracked_run(cmd, check=True)
            return chunk_idx

        if update_progress_cb:
            update_progress_cb(f"Super Keyframe parallel encoding ({actual_chunks}x NVENC)", 95)

        with ThreadPoolExecutor(max_workers=actual_chunks) as executor:
            futures = [executor.submit(run_encode, idx, cmd) for idx, cmd in chunk_cmds]
            for f in futures:
                f.result()

        for cp in chunk_paths:
            if not os.path.exists(cp) or os.path.getsize(cp) == 0:
                raise Exception(f"Super Keyframe chunk export failed for {cp}")

        # Concat chunks losslessly
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for cp in chunk_paths:
                f.write(f"file '{os.path.abspath(cp)}'\n")

        concat_cmd = [
            FFMPEG_EXE, "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy"
        ]
        if output_format == "mp4":
            concat_cmd.extend(["-f", "mp4"])
        elif output_format == "mkv":
            concat_cmd.extend(["-f", "matroska"])
        concat_cmd.append(output_file)

        print(f"\n{Fore.GREEN}[Super Keyframe] Joining {actual_chunks} chunks: {' '.join(concat_cmd)}{Style.RESET_ALL}")
        tracked_run(concat_cmd, check=True)

        print(f"{Fore.GREEN}[Super Keyframe] Parallel {actual_chunks}-stream NVENC encode completed successfully: {output_file}{Style.RESET_ALL}")
        return True

    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Super Keyframe parallel NVENC failed ({e}). Falling back to standard export.{Style.RESET_ALL}")
        return False
    finally:
        if os.path.exists(temp_chunk_dir):
            try:
                shutil.rmtree(temp_chunk_dir)
            except OSError:
                pass