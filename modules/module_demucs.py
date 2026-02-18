"""
Module for audio source separation using Demucs.
Includes segmentation logic for long files to prevent OOM/processing errors.
"""
import os
import subprocess
import sys
import tempfile
import shutil
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE

def separate_with_demucs(temp_audio_wav_path, demucs_base_out_path, base_audio_name_no_ext, max_workers=2):
    """
    Separates vocals using Demucs (htdemucs model).
    If audio is > 10 min, it splits the file into segments, processes them in parallel, and joins them back.
    
    Args:
        temp_audio_wav_path: Path to the source WAV file.
        demucs_base_out_path: Directory to store Demucs output.
        base_audio_name_no_ext: Base name for identifying output segments.
        max_workers: Number of parallel segments to process.
        
    Returns:
        tuple: (path_to_final_vocal_wav, temp_segments_dir)
    """
    print(f"\n{Fore.CYAN}3. Separating with Demucs (htdemucs model) into: {demucs_base_out_path}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Using up to {max_workers} parallel workers for Demucs segments.{Style.RESET_ALL}")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    demucs_vocal_wav_path = None
    temp_demucs_segments_dir = None
    try:
        os.makedirs(demucs_base_out_path, exist_ok=True)

        audio_duration = get_audio_duration(temp_audio_wav_path)
        if audio_duration is None:
            print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Demucs separation.{Style.RESET_ALL}")
            return None, None

        DEMUCS_SEGMENT_DURATION_SECONDS = 600  # 10 minutes per segment for GPU efficiency

        if audio_duration > DEMUCS_SEGMENT_DURATION_SECONDS:
            print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting audio for parallel Demucs...{Style.RESET_ALL}\n")
            # Ensure _temp exists
            os.makedirs("_temp", exist_ok=True)
            temp_demucs_segments_dir = tempfile.mkdtemp(dir="_temp")
            split_audio_paths = []

            current_start_time = 0
            segment_index = 0

            while current_start_time < audio_duration:
                segment_duration = min(DEMUCS_SEGMENT_DURATION_SECONDS, audio_duration - current_start_time)
                segment_filename = f"part_{segment_index:03d}.wav"
                segment_output_path = os.path.join(temp_demucs_segments_dir, segment_filename)

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

            print(f"\n{Fore.GREEN}\N{check mark} Audio splitted into {len(split_audio_paths)} segments for Demucs.{Style.RESET_ALL}")

            def process_segment(item):
                i, segment_path = item
                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                segment_vocal_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "vocals.wav")
                
                # Check if it already exists (maybe from a previous partial run?)
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    return i, segment_vocal_path
                
                demucs_cmd = [sys.executable, "-m", "demucs.separate", "-n", "htdemucs", "-o", demucs_base_out_path, segment_path]
                
                try:
                    subprocess.run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                except subprocess.CalledProcessError as e:
                    tqdm.write(f"{Fore.YELLOW}Warning: Demucs failed for segment {segment_base_name}. Creating silence.{Style.RESET_ALL}")
                    # Create silence fallback
                    os.makedirs(os.path.dirname(segment_vocal_path), exist_ok=True)
                    silence_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-i", segment_path, "-af", "volume=0", segment_vocal_path]
                    try:
                        subprocess.run(silence_cmd, check=True)
                    except:
                        return i, None
                
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    return i, segment_vocal_path
                return i, None

            # Execute in parallel
            results = [None] * len(split_audio_paths)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Map segments to worker tasks
                futures = {executor.submit(process_segment, (i, path)): i for i, path in enumerate(split_audio_paths)}
                
                with tqdm(total=len(split_audio_paths), desc="Demucs Parallel", unit="seg") as pbar:
                    for future in as_completed(futures):
                        idx, vocal_path = future.result()
                        results[idx] = vocal_path
                        pbar.update(1)

            demucs_segment_vocal_paths = [r for r in results if r is not None]

            if not demucs_segment_vocal_paths:
                print(f"{Fore.RED}Error: No Demucs vocal segments were successfully generated.{Style.RESET_ALL}")
                return None, temp_demucs_segments_dir
            else:
                # Joining segments...
                concat_list_path = os.path.join(temp_demucs_segments_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for p in demucs_segment_vocal_paths:
                        f.write(f"file '{os.path.abspath(p)}'\n")

                final_demucs_vocals_temp_path = os.path.join(temp_demucs_segments_dir, "concatenated_demucs_vocals.wav")
                
                ffmpeg_concat_cmd = [
                    FFMPEG_EXE, "-y", 
                    "-loglevel", "error",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    final_demucs_vocals_temp_path
                ]
                print(f"\nJoining Demucs vocal segments to: {final_demucs_vocals_temp_path}")
                subprocess.run(ffmpeg_concat_cmd, check=True)
                demucs_vocal_wav_path = final_demucs_vocals_temp_path
                print(f"\n{Fore.GREEN}\N{check mark} All Demucs vocal segments joined successfully.{Style.RESET_ALL}")
        else:
            # Short file, just run directly
            demucs_cmd = [
                sys.executable, "-m", "demucs.separate",
                "-n", "htdemucs",
                "-o", demucs_base_out_path,
                temp_audio_wav_path
            ]
            print(f"{Fore.MAGENTA}Executing: {' '.join(demucs_cmd)}\n{Style.RESET_ALL}")
            try: 
                subprocess.run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}Demucs failed for short audio. Creating silence fallback.{Style.RESET_ALL}")
                demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")
                os.makedirs(os.path.dirname(demucs_vocal_wav_path), exist_ok=True)
                silence_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-i", temp_audio_wav_path, "-af", "volume=0", demucs_vocal_wav_path]
                subprocess.run(silence_cmd, check=True)

            print(f"\n{Fore.GREEN}\N{check mark} Demucs separation complete.\n{Style.RESET_ALL}")

        if not os.path.exists(demucs_vocal_wav_path) or os.path.getsize(demucs_vocal_wav_path) == 0:
            print(f"{Fore.YELLOW}Warning: Demucs vocals not found or empty at {demucs_vocal_wav_path}.{Style.RESET_ALL}")
            return None, temp_demucs_segments_dir

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with demucs separation: {e}{Style.RESET_ALL}")
        # If there's a CalledProcessError, return None to indicate failure but allow process to continue
        return None, temp_demucs_segments_dir
    except Exception as e:
        print(f"{Fore.RED}Unexpected error with demucs separation: {e}{Style.RESET_ALL}")
        # For other exceptions (like AssertionError from silence), return None to allow process to continue
        return None, temp_demucs_segments_dir
    
    return demucs_vocal_wav_path, temp_demucs_segments_dir