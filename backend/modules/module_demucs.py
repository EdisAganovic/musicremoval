"""
MODULE: module_demucs.py - Demucs AI MODEL WRAPPER

ROLE: Separates vocals using Facebook's Demucs (htdemucs model)

RESPONSIBILITIES:
  - Runs Demucs source separation on audio files
  - Splits audio >10min into 600s segments for parallel processing
  - Handles OOM prevention via segmentation
  - Creates silence fallback on model failure

KEY FUNCTIONS:
  separate_with_demucs(temp_audio_wav_path, demucs_base_out_path, 
                       base_audio_name_no_ext, max_workers) → tuple
    - Returns: (path_to_vocal_wav, temp_segments_dir)
    - max_workers: Parallel segment processing (default: 2)

SEGMENTATION STRATEGY:
  - Files ≤10min: Process directly
  - Files >10min: Split into 600s chunks, process in parallel, concatenate

OUTPUT:
  - Saves to demucs_out/htdemucs/<basename>/vocals.wav
  - Temp segments stored in _temp/ (caller responsible for cleanup)

DEPENDENCIES:
  - module_ffmpeg: get_audio_duration(), FFMPEG_EXE for splitting/concatenation

MODEL:
  - Uses htdemucs (hybrid transformer Demucs)
  - Command: python -m demucs.separate -n htdemucs -o <output> <input>
"""
import os
import subprocess
import sys
import tempfile
import shutil
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, split_audio_into_segments

# Use tracked subprocess to prevent zombie processes on app exit
try:
    from services.process_manager import tracked_run
except ImportError:
    # Fallback if running standalone (e.g. from CLI main.py)
    tracked_run = subprocess.run

def separate_with_demucs(temp_audio_wav_path, demucs_base_out_path, base_audio_name_no_ext, max_workers=2, pre_split_segments=None, want_instrumental=False):
    """
    Separates vocals using Demucs (htdemucs model).
    If audio is > 10 min, it splits the file into segments, processes them in parallel, and joins them back.

    Args:
        temp_audio_wav_path: Path to the source WAV file.
        demucs_base_out_path: Directory to store Demucs output.
        base_audio_name_no_ext: Base name for identifying output segments.
        max_workers: Number of parallel segments to process.
        pre_split_segments: Optional list of pre-split audio segment paths.
        want_instrumental: If True, also produce a "no_vocals" (instrumental) track
            via demucs's --two-stems mode. When False, behavior/output is identical
            to before this option existed.

    Returns:
        tuple: (path_to_final_vocal_wav, path_to_final_instrumental_wav_or_None, temp_demucs_segments_dir)
    """
    print(f"\n{Fore.CYAN}3. Separating with Demucs (htdemucs model) into: {demucs_base_out_path}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Using up to {max_workers} parallel workers for Demucs segments.{Style.RESET_ALL}")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    demucs_vocal_wav_path = None
    demucs_instrumental_wav_path = None
    temp_demucs_segments_dir = None
    try:
        os.makedirs(demucs_base_out_path, exist_ok=True)

        audio_duration = get_audio_duration(temp_audio_wav_path)
        if audio_duration is None:
            print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Demucs separation.{Style.RESET_ALL}")
            return None, None, None

        DEMUCS_SEGMENT_DURATION_SECONDS = 600  # 10 minutes per segment for GPU efficiency

        # Check if we should use pre-split segments or split ourselves
        if pre_split_segments:
            print(f"{Fore.GREEN}Using {len(pre_split_segments)} pre-split segments for Demucs.{Style.RESET_ALL}")
            split_audio_paths = pre_split_segments
            # No need to create a temp dir for splitting, but we might need it for concat_list.txt
            temp_demucs_segments_dir = tempfile.mkdtemp(dir="_temp")
        elif audio_duration > DEMUCS_SEGMENT_DURATION_SECONDS:
            print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting audio for parallel Demucs...{Style.RESET_ALL}\n")
            temp_demucs_segments_dir, split_audio_paths = split_audio_into_segments(
                temp_audio_wav_path, audio_duration, DEMUCS_SEGMENT_DURATION_SECONDS
            )
            print(f"\n{Fore.GREEN}[OK] Audio splitted into {len(split_audio_paths)} segments for Demucs.{Style.RESET_ALL}")
        
        # Determine if we should process in parallel (if we have segments)
        if pre_split_segments or (audio_duration > DEMUCS_SEGMENT_DURATION_SECONDS):

            def process_segment(item):
                i, segment_path = item
                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                segment_vocal_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "vocals.wav")
                segment_no_vocals_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "no_vocals.wav")

                # Check if it already exists (maybe from a previous partial run?)
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    return i, segment_vocal_path, (segment_no_vocals_path if os.path.exists(segment_no_vocals_path) else None)

                from modules.module_ffmpeg_shared import _find_shared_bin_dir
                shared_bin = _find_shared_bin_dir()
                two_stems_args = ["--two-stems", "vocals"] if want_instrumental else []
                if shared_bin and sys.platform == "win32":
                    demucs_cmd = [
                        sys.executable, "-c",
                        f"import os; os.add_dll_directory(r'{shared_bin}'); from demucs.separate import main; main()",
                        "-n", "htdemucs", *two_stems_args, "-o", demucs_base_out_path, segment_path
                    ]
                else:
                    demucs_cmd = [sys.executable, "-m", "demucs.separate", "-n", "htdemucs", *two_stems_args, "-o", demucs_base_out_path, segment_path]

                try:
                    tracked_run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                except subprocess.CalledProcessError as e:
                    tqdm.write(f"{Fore.YELLOW}Warning: Demucs failed for segment {segment_base_name}.{Style.RESET_ALL}")
                    if e.stderr:
                        tqdm.write(f"{Fore.RED}Demucs Error: {e.stderr[:500]}{Style.RESET_ALL}")
                    # Create silence fallback
                    os.makedirs(os.path.dirname(segment_vocal_path), exist_ok=True)
                    silence_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-i", segment_path, "-af", "volume=0", segment_vocal_path]
                    try:
                        tracked_run(silence_cmd, check=True)
                    except (subprocess.CalledProcessError, OSError):
                        return i, None, None

                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    no_vocals = segment_no_vocals_path if (want_instrumental and os.path.exists(segment_no_vocals_path) and os.path.getsize(segment_no_vocals_path) > 0) else None
                    return i, segment_vocal_path, no_vocals
                return i, None, None

            # Execute in parallel
            results = [None] * len(split_audio_paths)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Map segments to worker tasks
                futures = {executor.submit(process_segment, (i, path)): i for i, path in enumerate(split_audio_paths)}

                with tqdm(total=len(split_audio_paths), desc="Demucs Parallel", unit="seg") as pbar:
                    for future in as_completed(futures):
                        idx, vocal_path, no_vocals_path = future.result()
                        results[idx] = (vocal_path, no_vocals_path)
                        pbar.update(1)

            demucs_segment_vocal_paths = [r[0] for r in results if r[0] is not None]
            demucs_segment_no_vocals_paths = [r[1] for r in results if r[0] is not None]

            if not demucs_segment_vocal_paths:
                print(f"{Fore.RED}Error: No Demucs vocal segments were successfully generated.{Style.RESET_ALL}")
                return None, None, temp_demucs_segments_dir
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
                tracked_run(ffmpeg_concat_cmd, check=True)
                demucs_vocal_wav_path = final_demucs_vocals_temp_path
                print(f"\n{Fore.GREEN}[OK] All Demucs vocal segments joined successfully.{Style.RESET_ALL}")

                # Same concatenation, for the instrumental/no_vocals segments (if requested and all present)
                if want_instrumental and len(demucs_segment_no_vocals_paths) == len(demucs_segment_vocal_paths) and all(demucs_segment_no_vocals_paths):
                    no_vocals_concat_list_path = os.path.join(temp_demucs_segments_dir, "concat_list_no_vocals.txt")
                    with open(no_vocals_concat_list_path, "w") as f:
                        for p in demucs_segment_no_vocals_paths:
                            f.write(f"file '{os.path.abspath(p)}'\n")

                    final_demucs_no_vocals_temp_path = os.path.join(temp_demucs_segments_dir, "concatenated_demucs_no_vocals.wav")
                    ffmpeg_concat_no_vocals_cmd = [
                        FFMPEG_EXE, "-y",
                        "-loglevel", "error",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", no_vocals_concat_list_path,
                        "-c", "copy",
                        final_demucs_no_vocals_temp_path
                    ]
                    try:
                        tracked_run(ffmpeg_concat_no_vocals_cmd, check=True)
                        demucs_instrumental_wav_path = final_demucs_no_vocals_temp_path
                        print(f"{Fore.GREEN}[OK] All Demucs instrumental segments joined successfully.{Style.RESET_ALL}")
                    except subprocess.CalledProcessError as e:
                        print(f"{Fore.YELLOW}Warning: Failed to join instrumental segments, skipping instrumental output: {e}{Style.RESET_ALL}")
        else:
            # Short file, just run directly
            from modules.module_ffmpeg_shared import _find_shared_bin_dir
            shared_bin = _find_shared_bin_dir()
            two_stems_args = ["--two-stems", "vocals"] if want_instrumental else []
            if shared_bin and sys.platform == "win32":
                demucs_cmd = [
                    sys.executable, "-c",
                    f"import os; os.add_dll_directory(r'{shared_bin}'); from demucs.separate import main; main()",
                    "-n", "htdemucs", *two_stems_args, "-o", demucs_base_out_path, temp_audio_wav_path
                ]
            else:
                demucs_cmd = [
                    sys.executable, "-m", "demucs.separate",
                    "-n", "htdemucs", *two_stems_args,
                    "-o", demucs_base_out_path,
                    temp_audio_wav_path
                ]
            print(f"{Fore.MAGENTA}Executing: {' '.join(demucs_cmd)}\n{Style.RESET_ALL}")
            try:
                tracked_run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")
                candidate_no_vocals = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "no_vocals.wav")
                if want_instrumental and os.path.exists(candidate_no_vocals) and os.path.getsize(candidate_no_vocals) > 0:
                    demucs_instrumental_wav_path = candidate_no_vocals
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}Demucs failed!{Style.RESET_ALL}")
                if e.stderr:
                    print(f"{Fore.RED}Demucs Error Output:\n{e.stderr}{Style.RESET_ALL}")

                print(f"{Fore.YELLOW}Creating silence fallback for: {base_audio_name_no_ext}{Style.RESET_ALL}")
                demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")
                os.makedirs(os.path.dirname(demucs_vocal_wav_path), exist_ok=True)
                silence_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-i", temp_audio_wav_path, "-af", "volume=0", demucs_vocal_wav_path]
                tracked_run(silence_cmd, check=True)

            print(f"\n{Fore.GREEN}[OK] Demucs separation complete.\n{Style.RESET_ALL}")

        if not os.path.exists(demucs_vocal_wav_path) or os.path.getsize(demucs_vocal_wav_path) == 0:
            print(f"{Fore.YELLOW}Warning: Demucs vocals not found or empty at {demucs_vocal_wav_path}.{Style.RESET_ALL}")
            return None, None, temp_demucs_segments_dir

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with demucs separation: {e}{Style.RESET_ALL}")
        # If there's a CalledProcessError, return None to indicate failure but allow process to continue
        return None, None, temp_demucs_segments_dir
    except Exception as e:
        print(f"{Fore.RED}Unexpected error with demucs separation: {e}{Style.RESET_ALL}")
        # For other exceptions (like AssertionError from silence), return None to allow process to continue
        return None, None, temp_demucs_segments_dir

    return demucs_vocal_wav_path, demucs_instrumental_wav_path, temp_demucs_segments_dir