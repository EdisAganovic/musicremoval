"""
MODULE: module_spleeter.py - Spleeter AI MODEL WRAPPER

ROLE: Separates vocals using Deezer's Spleeter (2stems model)

RESPONSIBILITIES:
  - Runs Spleeter source separation on audio files
  - Splits audio >10min into 600s segments for processing
  - Handles long audio files that would cause memory issues

KEY FUNCTIONS:
  separate_with_spleeter(temp_audio_wav_path, spleeter_out_path, 
                         base_audio_name_no_ext) → tuple
    - Returns: (path_to_vocal_wav, temp_segments_dir)
    - Returns (None, None) on failure

SEGMENTATION STRATEGY:
  - Files ≤10min: Process directly
  - Files >10min: Split into 600s chunks, process sequentially, concatenate

OUTPUT:
  - Saves to spleeter_out/<basename>/vocals.wav
  - Temp segments stored in _temp/ (caller responsible for cleanup)

DEPENDENCIES:
  - module_ffmpeg: get_audio_duration(), FFMPEG_EXE for splitting/concatenation

MODEL:
  - Uses spleeter:2stems (vocals + accompaniment)
  - Command: python -m spleeter separate -p spleeter:2stems -o <output> <input>
"""
import os
import subprocess
import sys
import tempfile
import concurrent.futures
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, split_audio_into_segments

# Use tracked subprocess to prevent zombie processes on app exit
try:
    from services.process_manager import tracked_run
except ImportError:
    tracked_run = subprocess.run

def get_spleeter_workers():
    """Reads the number of Spleeter workers from data/video.json."""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "video.json"))
    default_workers = 4
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, "r") as f:
                data = json.load(f)
                return data.get("processing", {}).get("spleeter_workers", default_workers)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not read Spleeter workers from video.json ({e}). Using default: {default_workers}{Style.RESET_ALL}")
    return default_workers

SPLEETER_IMAGE = "deezer/spleeter:3.6-2stems"
MAX_WORKERS = get_spleeter_workers()
# Path on host for pretrained models
MODEL_DIRECTORY_HOST = os.path.abspath("pretrained_models")

def is_docker_available():
    """Checks if Docker is running and the required Spleeter image is present."""
    try:
        # Check if docker is running
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        # Check if the image exists
        result = subprocess.run(["docker", "images", "-q", SPLEETER_IMAGE], check=True, capture_output=True, text=True)
        if result.stdout.strip():
            return True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def separate_with_spleeter(temp_audio_wav_path, spleeter_out_path, base_audio_name_no_ext, pre_split_segments=None, want_instrumental=False):
    """
    Separates vocals using Spleeter (2stems model) via subprocess.
    Handles long audio files by splitting them into chunks.

    Spleeter's 2stems mode always produces an accompaniment.wav alongside
    vocals.wav (no extra flag/compute needed) - want_instrumental just controls
    whether we bother tracking/concatenating it into a usable instrumental track.

    Returns:
        tuple: (path_to_final_vocal_wav, path_to_final_instrumental_wav_or_None, temp_segments_dir)
    """
    print(f"{Fore.CYAN}2. Separating with Spleeter...{Style.RESET_ALL}")
    spleeter_vocal_wav_path = None
    spleeter_instrumental_wav_path = None
    temp_spleeter_segments_dir = None
    try:
        os.makedirs(spleeter_out_path, exist_ok=True)

        audio_duration = get_audio_duration(temp_audio_wav_path)
        if audio_duration is None:
            print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Spleeter separation.{Style.RESET_ALL}")
            return None, None, None

        SPLEETER_SEGMENT_DURATION_SECONDS = 600  # 10 minutes

        # Check if we should use pre-split segments or split ourselves
        if pre_split_segments:
            print(f"{Fore.GREEN}Using {len(pre_split_segments)} pre-split segments for Spleeter.{Style.RESET_ALL}")
            split_audio_paths = pre_split_segments
            # No need to create a temp dir for splitting, but we might need it for concat_list.txt
            temp_spleeter_segments_dir = tempfile.mkdtemp(dir="_temp")
        elif audio_duration > SPLEETER_SEGMENT_DURATION_SECONDS:
            print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting audio for Spleeter...{Style.RESET_ALL}\n")
            temp_spleeter_segments_dir, split_audio_paths = split_audio_into_segments(
                temp_audio_wav_path, audio_duration, SPLEETER_SEGMENT_DURATION_SECONDS
            )
            print(f"\n{Fore.GREEN}[OK] Audio splitted into {len(split_audio_paths)} segments for Spleeter.{Style.RESET_ALL}")
        
        # If we have segments (either pre-split or just split)
        if (pre_split_segments or (audio_duration > SPLEETER_SEGMENT_DURATION_SECONDS)):
            spleeter_segment_vocal_paths = []
            spleeter_segment_no_vocals_map = {}

            use_docker = is_docker_available()
            if use_docker:
                print(f"{Fore.GREEN}Docker detected. Using {SPLEETER_IMAGE} with {MAX_WORKERS} workers.{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Docker not available or image missing. Falling back to local Spleeter.{Style.RESET_ALL}")

            def process_segment(i, segment_path):
                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                
                if use_docker:
                    input_dir = os.path.dirname(os.path.abspath(segment_path))
                    input_file = os.path.basename(segment_path)
                    output_dir_abs = os.path.abspath(spleeter_out_path)
                    
                    spleeter_cmd = [
                        "docker", "run", "--rm",
                        "-v", f"{input_dir}:/input",
                        "-v", f"{output_dir_abs}:/output",
                        "-v", f"{MODEL_DIRECTORY_HOST}:/model",
                        "-e", "MODEL_PATH=/model",
                        SPLEETER_IMAGE,
                        "separate", "-p", "spleeter:2stems", "-o", "/output", f"/input/{input_file}"
                    ]
                else:
                    spleeter_cmd = [sys.executable, "-m", "spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, segment_path]
                
                env = os.environ.copy()
                if not use_docker:
                    env["MODEL_PATH"] = MODEL_DIRECTORY_HOST
                
                try:
                    res = tracked_run(spleeter_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
                except subprocess.CalledProcessError as e:
                    err_msg = e.stderr or e.stdout or str(e)
                    print(f"\n{Fore.RED}{'='*70}")
                    print(f"[FATAL CHUNK ERROR] Spleeter failed on Segment {i+1}/{len(split_audio_paths)}")
                    print(f"Segment Audio File: {segment_path}")
                    print(f"Command Executed: {' '.join(spleeter_cmd)}")
                    print(f"Error Details:\n{err_msg}")
                    print(f"{'='*70}{Style.RESET_ALL}\n")
                    raise RuntimeError(f"Spleeter failed on segment {i+1} ({os.path.basename(segment_path)}): {err_msg[:300]}")
                except Exception as e:
                    print(f"\n{Fore.RED}[FATAL CHUNK ERROR] Spleeter unexpected error on Segment {i+1}: {e}{Style.RESET_ALL}\n")
                    raise

                segment_vocal_path = os.path.join(spleeter_out_path, segment_base_name, "vocals.wav")
                segment_no_vocals_path = os.path.join(spleeter_out_path, segment_base_name, "accompaniment.wav")

                if not (os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 1024):
                    print(f"\n{Fore.RED}{'='*70}")
                    print(f"[FATAL CHUNK ERROR] Spleeter produced missing or empty vocals on Segment {i+1}")
                    print(f"Expected File: {segment_vocal_path}")
                    print(f"Source Segment: {segment_path}")
                    print(f"{'='*70}{Style.RESET_ALL}\n")
                    raise RuntimeError(f"Spleeter produced empty vocals on segment {i+1} ({os.path.basename(segment_path)})")

                return segment_vocal_path, segment_no_vocals_path

            # Use ThreadPoolExecutor for parallel processing
            workers = get_spleeter_workers()
            results = [None] * len(split_audio_paths)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(process_segment, i, path): (i, path) for i, path in enumerate(split_audio_paths)}
                for future in tqdm(concurrent.futures.as_completed(futures), total=len(split_audio_paths), desc="Spleeter segments", unit="seg"):
                    i, segment_path = futures[future]
                    segment_vocal_path, segment_no_vocals_path = future.result()
                    results[i] = (segment_vocal_path, segment_no_vocals_path)

            spleeter_segment_vocal_paths = [r[0] for r in results if r and r[0]]
            spleeter_segment_no_vocals_paths = [r[1] for r in results if r and r[1]]

            if len(spleeter_segment_vocal_paths) != len(split_audio_paths):
                print(f"{Fore.RED}Critical Error: Only {len(spleeter_segment_vocal_paths)}/{len(split_audio_paths)} Spleeter vocal segments exist.{Style.RESET_ALL}")
                return None, None, temp_spleeter_segments_dir
            else:
                concat_list_path = os.path.join(temp_spleeter_segments_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for p in spleeter_segment_vocal_paths:
                        f.write(f"file '{os.path.abspath(p)}'\n")

                final_spleeter_vocals_temp_path = os.path.join(temp_spleeter_segments_dir, "concatenated_spleeter_vocals.wav")
                ffmpeg_concat_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", final_spleeter_vocals_temp_path]
                tracked_run(ffmpeg_concat_cmd, check=True)
                spleeter_vocal_wav_path = final_spleeter_vocals_temp_path
                print(f"\n{Fore.GREEN}[OK] All {len(spleeter_segment_vocal_paths)} Spleeter vocal segments verified and joined successfully.{Style.RESET_ALL}")

                # Same concatenation for the instrumental/accompaniment segments
                if want_instrumental and len(spleeter_segment_no_vocals_paths) == len(split_audio_paths):
                    no_vocals_concat_list_path = os.path.join(temp_spleeter_segments_dir, "concat_list_accompaniment.txt")
                    with open(no_vocals_concat_list_path, "w") as f:
                        for p in spleeter_segment_no_vocals_paths:
                            f.write(f"file '{os.path.abspath(p)}'\n")

                    final_spleeter_no_vocals_temp_path = os.path.join(temp_spleeter_segments_dir, "concatenated_spleeter_accompaniment.wav")
                    ffmpeg_concat_no_vocals_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", no_vocals_concat_list_path, "-c", "copy", final_spleeter_no_vocals_temp_path]
                    try:
                        tracked_run(ffmpeg_concat_no_vocals_cmd, check=True)
                        spleeter_instrumental_wav_path = final_spleeter_no_vocals_temp_path
                        print(f"{Fore.GREEN}[OK] All Spleeter instrumental segments joined successfully.{Style.RESET_ALL}")
                    except subprocess.CalledProcessError as e:
                        print(f"{Fore.YELLOW}Warning: Failed to join Spleeter instrumental segments: {e}{Style.RESET_ALL}")
        else:
            use_docker = is_docker_available()
            if use_docker:
                print(f"{Fore.GREEN}Docker detected. Using {SPLEETER_IMAGE} for single file.{Style.RESET_ALL}")
                input_dir = os.path.dirname(os.path.abspath(temp_audio_wav_path))
                input_file = os.path.basename(temp_audio_wav_path)
                output_dir_abs = os.path.abspath(spleeter_out_path)
                spleeter_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{input_dir}:/input",
                    "-v", f"{output_dir_abs}:/output",
                    "-v", f"{MODEL_DIRECTORY_HOST}:/model",
                    "-e", "MODEL_PATH=/model",
                    SPLEETER_IMAGE,
                    "separate", "-p", "spleeter:2stems", "-o", "/output", f"/input/{input_file}"
                ]
            else:
                spleeter_cmd = [sys.executable, "-m", "spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, temp_audio_wav_path]
            
            print(f"{Fore.MAGENTA}Executing: {' '.join(spleeter_cmd)}{Style.RESET_ALL}\n")
            
            # Set up environment for local spleeter to find models
            env = os.environ.copy()
            if not use_docker:
                env["MODEL_PATH"] = MODEL_DIRECTORY_HOST
            
            tracked_run(spleeter_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            actual_name = os.path.splitext(os.path.basename(temp_audio_wav_path))[0]
            candidate_dirs = [
                os.path.join(spleeter_out_path, actual_name),
                os.path.join(spleeter_out_path, base_audio_name_no_ext)
            ]
            if os.path.exists(spleeter_out_path):
                for sub in os.listdir(spleeter_out_path):
                    p = os.path.join(spleeter_out_path, sub)
                    if os.path.isdir(p) and p not in candidate_dirs:
                        candidate_dirs.append(p)

            found_dir = None
            for c_dir in candidate_dirs:
                if os.path.exists(os.path.join(c_dir, "vocals.wav")):
                    found_dir = c_dir
                    break

            if found_dir:
                spleeter_vocal_wav_path = os.path.join(found_dir, "vocals.wav")
                candidate_accompaniment = os.path.join(found_dir, "accompaniment.wav")
                if want_instrumental and os.path.exists(candidate_accompaniment) and os.path.getsize(candidate_accompaniment) > 0:
                    spleeter_instrumental_wav_path = candidate_accompaniment
            else:
                spleeter_vocal_wav_path = os.path.join(spleeter_out_path, base_audio_name_no_ext, "vocals.wav")
            print(f"{Fore.GREEN}Spleeter separation complete.{Style.RESET_ALL}")

        if spleeter_vocal_wav_path and not (os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0):
            print(f"{Fore.YELLOW}Warning: Final Spleeter vocals not found or empty at {spleeter_vocal_wav_path}. This might be expected if Spleeter failed.{Style.RESET_ALL}")
            spleeter_vocal_wav_path = None

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with spleeter separation: {e}{Style.RESET_ALL}")
        if e.stderr:
            print(f"{Fore.RED}Spleeter Error Output: {e.stderr}{Style.RESET_ALL}")
        spleeter_vocal_wav_path = None
        spleeter_instrumental_wav_path = None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during Spleeter processing: {e}{Style.RESET_ALL}")
        spleeter_vocal_wav_path = None
        spleeter_instrumental_wav_path = None

    return spleeter_vocal_wav_path, spleeter_instrumental_wav_path, temp_spleeter_segments_dir
