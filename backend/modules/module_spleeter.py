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
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE

def separate_with_spleeter(temp_audio_wav_path, spleeter_out_path, base_audio_name_no_ext):
    """
    Separates vocals using Spleeter (2stems model) via subprocess.
    Handles long audio files by splitting them into chunks.
    
    Returns:
        tuple: (path_to_final_vocal_wav, temp_segments_dir)
    """
    print(f"{Fore.CYAN}2. Separating with Spleeter...{Style.RESET_ALL}")
    spleeter_vocal_wav_path = None
    temp_spleeter_segments_dir = None
    try:
        os.makedirs(spleeter_out_path, exist_ok=True)

        audio_duration = get_audio_duration(temp_audio_wav_path)
        if audio_duration is None:
            print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Spleeter separation.{Style.RESET_ALL}")
            return None, None

        SPLEETER_SEGMENT_DURATION_SECONDS = 600  # 10 minutes

        if audio_duration > SPLEETER_SEGMENT_DURATION_SECONDS:
            print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting audio for Spleeter...{Style.RESET_ALL}\n")
            # Ensure _temp exists
            os.makedirs("_temp", exist_ok=True)
            temp_spleeter_segments_dir = tempfile.mkdtemp(dir="_temp")
            spleeter_segment_vocal_paths = []
            split_audio_paths = []

            current_start_time = 0
            segment_index = 0

            while current_start_time < audio_duration:
                segment_duration = min(SPLEETER_SEGMENT_DURATION_SECONDS, audio_duration - current_start_time)
                segment_filename = f"part_{segment_index:03d}.wav"
                segment_output_path = os.path.join(temp_spleeter_segments_dir, segment_filename)

                ffmpeg_split_cmd = [
                    FFMPEG_EXE, "-y", 
                    "-loglevel", "error",
                    "-i", temp_audio_wav_path,
                    "-ss", str(current_start_time),
                    "-t", str(segment_duration),
                    segment_output_path
                ]
                print(f"- Splitting audio: {segment_filename} from {current_start_time:.2f}s for {segment_duration:.2f}s...")
                subprocess.run(ffmpeg_split_cmd, check=True)
                split_audio_paths.append(segment_output_path)

                current_start_time += segment_duration
                segment_index += 1

            print(f"\n{Fore.GREEN}\N{check mark} Audio splitted into {len(split_audio_paths)} segments for Spleeter.{Style.RESET_ALL}")

            for i, segment_path in tqdm(enumerate(split_audio_paths), total=len(split_audio_paths), desc="Spleeter segments", unit="seg"):
                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                
                spleeter_cmd = [sys.executable, "-m", "spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, segment_path]
                tqdm.write(f"{Fore.MAGENTA}Processing segment {i+1}/{len(split_audio_paths)} with Spleeter{Style.RESET_ALL}")
                subprocess.run(spleeter_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

                segment_vocal_path = os.path.join(spleeter_out_path, segment_base_name, "vocals.wav")
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    spleeter_segment_vocal_paths.append(segment_vocal_path)
                else:
                    print(f"{Fore.YELLOW}Warning: Spleeter vocals for segment {segment_base_name} not found or empty. Skipping.{Style.RESET_ALL}")

            if not spleeter_segment_vocal_paths:
                print(f"{Fore.RED}Error: No Spleeter vocal segments generated.{Style.RESET_ALL}")
                return None, temp_spleeter_segments_dir
            else:
                concat_list_path = os.path.join(temp_spleeter_segments_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for p in spleeter_segment_vocal_paths:
                        f.write(f"file '{os.path.abspath(p)}'\n")

                final_spleeter_vocals_temp_path = os.path.join(temp_spleeter_segments_dir, "concatenated_spleeter_vocals.wav")
                ffmpeg_concat_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", final_spleeter_vocals_temp_path]
                subprocess.run(ffmpeg_concat_cmd, check=True)
                spleeter_vocal_wav_path = final_spleeter_vocals_temp_path
                print(f"\n{Fore.GREEN}\N{check mark} All Spleeter vocal segments joined successfully.{Style.RESET_ALL}")
        else:
            spleeter_cmd = [sys.executable, "-m", "spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, temp_audio_wav_path]
            print(f"{Fore.MAGENTA}Executing: {' '.join(spleeter_cmd)}{Style.RESET_ALL}\n")
            subprocess.run(spleeter_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            spleeter_vocal_wav_path = os.path.join(spleeter_out_path, base_audio_name_no_ext, "vocals.wav")
            print(f"{Fore.GREEN}Spleeter separation complete.{Style.RESET_ALL}")
        
        if spleeter_vocal_wav_path and not (os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0):
            print(f"{Fore.YELLOW}Warning: Final Spleeter vocals not found or empty at {spleeter_vocal_wav_path}. This might be expected if Spleeter failed.{Style.RESET_ALL}")
            spleeter_vocal_wav_path = None

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with spleeter separation: {e}{Style.RESET_ALL}")
        spleeter_vocal_wav_path = None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during Spleeter processing: {e}{Style.RESET_ALL}")
        spleeter_vocal_wav_path = None
    
    return spleeter_vocal_wav_path, temp_spleeter_segments_dir
