"""
MODULE: module_demucs.py - Demucs AI MODEL WRAPPER (MULTI-GPU ACCELERATED)

ROLE: Separates vocals using Facebook's Demucs (htdemucs model)
      Supports multi-GPU segment distribution across available CUDA devices (e.g. cuda:0 & cuda:1).
"""
import os
import subprocess
import sys
import tempfile
import shutil
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, split_audio_into_segments
from module_cuda import get_available_cuda_devices

try:
    from services.process_manager import tracked_run
except ImportError:
    tracked_run = subprocess.run


def separate_with_demucs(
    temp_audio_wav_path,
    demucs_base_out_path,
    base_audio_name_no_ext,
    max_workers=None,
    pre_split_segments=None,
    want_instrumental=False,
    device=None
):
    """
    Separates vocals using Demucs (htdemucs model).
    If audio is > 10 min, it splits the file into segments, processes them in parallel across
    all available GPUs (cuda:0, cuda:1, etc.), and joins them back.

    Args:
        temp_audio_wav_path: Path to the source WAV file.
        demucs_base_out_path: Directory to store Demucs output.
        base_audio_name_no_ext: Base name for identifying output segments.
        max_workers: Number of parallel segments to process (defaults to number of GPUs).
        pre_split_segments: Optional list of pre-split audio segment paths.
        want_instrumental: If True, also produce a "no_vocals" (instrumental) track.
        device: Explicit device override (e.g. 'cuda:0'). If None, dynamically distributes.

    Returns:
        tuple: (path_to_final_vocal_wav, path_to_final_instrumental_wav_or_None, temp_demucs_segments_dir)
    """
    available_devices = get_available_cuda_devices()
    if max_workers is None:
        # Default parallel workers = number of available GPUs
        max_workers = max(1, len(available_devices))

    print(f"\n{Fore.CYAN}3. Separating with Demucs (htdemucs model) into: {demucs_base_out_path}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Available Devices: {', '.join(available_devices)} | Max Parallel Workers: {max_workers}{Style.RESET_ALL}")

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

        DEMUCS_SEGMENT_DURATION_SECONDS = 600  # 10 minutes per segment

        # Check if we should use pre-split segments or split ourselves
        if pre_split_segments:
            print(f"{Fore.GREEN}Using {len(pre_split_segments)} pre-split segments for Demucs.{Style.RESET_ALL}")
            split_audio_paths = pre_split_segments
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
                # Round-robin assign segments across available GPUs
                seg_device = device if device else available_devices[i % len(available_devices)]

                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                segment_vocal_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "vocals.wav")
                segment_no_vocals_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "no_vocals.wav")

                # Check if it already exists
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    return i, segment_vocal_path, (segment_no_vocals_path if os.path.exists(segment_no_vocals_path) else None)

                from modules.module_ffmpeg_shared import _find_shared_bin_dir
                shared_bin = _find_shared_bin_dir()
                two_stems_args = ["--two-stems", "vocals"]
                device_arg = ["-d", seg_device]

                if shared_bin and sys.platform == "win32":
                    demucs_cmd = [
                        sys.executable, "-c",
                        f"import os; os.add_dll_directory(r'{shared_bin}'); from demucs.separate import main; main()",
                        "-n", "htdemucs", *two_stems_args, *device_arg, "-o", demucs_base_out_path, segment_path
                    ]
                else:
                    demucs_cmd = [sys.executable, "-m", "demucs.separate", "-n", "htdemucs", *two_stems_args, *device_arg, "-o", demucs_base_out_path, segment_path]

                print(f"{Fore.CYAN}[Segment {i+1}/{len(split_audio_paths)}] Running on {seg_device}...{Style.RESET_ALL}")
                try:
                    tracked_run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                except subprocess.CalledProcessError as e:
                    err_msg = e.stderr or e.stdout or str(e)
                    print(f"\n{Fore.RED}{'='*70}")
                    print(f"[FATAL CHUNK ERROR] Demucs failed on Segment {i+1}/{len(split_audio_paths)} on {seg_device}")
                    print(f"Segment Audio File: {segment_path}")
                    print(f"Command Executed: {' '.join(demucs_cmd)}")
                    print(f"Error Details:\n{err_msg}")
                    print(f"{'='*70}{Style.RESET_ALL}\n")
                    raise RuntimeError(f"Demucs failed on segment {i+1} on {seg_device}: {err_msg[:300]}")
                except Exception as e:
                    print(f"\n{Fore.RED}[FATAL CHUNK ERROR] Demucs unexpected error on Segment {i+1}: {e}{Style.RESET_ALL}\n")
                    raise

                if not (os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 1024):
                    print(f"\n{Fore.RED}{'='*70}")
                    print(f"[FATAL CHUNK ERROR] Demucs produced missing or empty vocals on Segment {i+1}")
                    print(f"Expected File: {segment_vocal_path}")
                    print(f"Source Segment: {segment_path}")
                    print(f"{'='*70}{Style.RESET_ALL}\n")
                    raise RuntimeError(f"Demucs produced empty vocals on segment {i+1} ({os.path.basename(segment_path)})")

                no_vocals = segment_no_vocals_path if (want_instrumental and os.path.exists(segment_no_vocals_path) and os.path.getsize(segment_no_vocals_path) > 0) else None
                return i, segment_vocal_path, no_vocals

            # Execute in parallel across GPUs
            results = [None] * len(split_audio_paths)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_segment, (i, path)): (i, path) for i, path in enumerate(split_audio_paths)}

                with tqdm(total=len(split_audio_paths), desc="Demucs Multi-GPU", unit="seg") as pbar:
                    for future in as_completed(futures):
                        i, segment_path = futures[future]
                        idx, vocal_path, no_vocals_path = future.result()
                        results[i] = (vocal_path, no_vocals_path)
                        pbar.update(1)

            demucs_segment_vocal_paths = [r[0] for r in results if r and r[0]]
            demucs_segment_no_vocals_paths = [r[1] for r in results if r and r[1]]

            if len(demucs_segment_vocal_paths) != len(split_audio_paths):
                print(f"{Fore.RED}Critical Error: Only {len(demucs_segment_vocal_paths)}/{len(split_audio_paths)} Demucs vocal segments exist.{Style.RESET_ALL}")
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
                print(f"\n{Fore.GREEN}[OK] All {len(demucs_segment_vocal_paths)} Demucs vocal segments verified and joined successfully.{Style.RESET_ALL}")

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
            # Single chunk/short file execution
            target_device = device if device else (available_devices[0] if available_devices else "cuda")
            from modules.module_ffmpeg_shared import _find_shared_bin_dir
            shared_bin = _find_shared_bin_dir()
            two_stems_args = ["--two-stems", "vocals"]
            device_arg = ["-d", target_device]

            if shared_bin and sys.platform == "win32":
                demucs_cmd = [
                    sys.executable, "-c",
                    f"import os; os.add_dll_directory(r'{shared_bin}'); from demucs.separate import main; main()",
                    "-n", "htdemucs", *two_stems_args, *device_arg, "-o", demucs_base_out_path, temp_audio_wav_path
                ]
            else:
                demucs_cmd = [
                    sys.executable, "-m", "demucs.separate",
                    "-n", "htdemucs", *two_stems_args, *device_arg,
                    "-o", demucs_base_out_path,
                    temp_audio_wav_path
                ]
            print(f"{Fore.MAGENTA}Executing Demucs on {target_device}: {' '.join(demucs_cmd)}\n{Style.RESET_ALL}")
            try:
                tracked_run(demucs_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                actual_name = os.path.splitext(os.path.basename(temp_audio_wav_path))[0]
                
                ht_dir = os.path.join(demucs_base_out_path, "htdemucs")
                candidate_dirs = [
                    os.path.join(ht_dir, actual_name),
                    os.path.join(ht_dir, base_audio_name_no_ext),
                ]
                if os.path.exists(ht_dir):
                    for sub in os.listdir(ht_dir):
                        p = os.path.join(ht_dir, sub)
                        if os.path.isdir(p) and p not in candidate_dirs:
                            candidate_dirs.append(p)

                found_dir = None
                for c_dir in candidate_dirs:
                    if os.path.exists(os.path.join(c_dir, "vocals.wav")):
                        found_dir = c_dir
                        break

                if found_dir:
                    demucs_vocal_wav_path = os.path.join(found_dir, "vocals.wav")
                    candidate_no_vocals = os.path.join(found_dir, "no_vocals.wav")
                    if want_instrumental and os.path.exists(candidate_no_vocals) and os.path.getsize(candidate_no_vocals) > 0:
                        demucs_instrumental_wav_path = candidate_no_vocals
                else:
                    demucs_vocal_wav_path = os.path.join(ht_dir, base_audio_name_no_ext, "vocals.wav")

            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}Demucs failed!{Style.RESET_ALL}")
                if e.stderr:
                    print(f"{Fore.RED}Demucs Error Output:\n{e.stderr}{Style.RESET_ALL}")
                demucs_vocal_wav_path = None
                raise

            print(f"\n{Fore.GREEN}[OK] Demucs separation complete on {target_device}.\n{Style.RESET_ALL}")

        if not demucs_vocal_wav_path or not os.path.exists(demucs_vocal_wav_path) or os.path.getsize(demucs_vocal_wav_path) == 0:
            print(f"{Fore.YELLOW}Warning: Demucs vocals not found or empty at {demucs_vocal_wav_path}.{Style.RESET_ALL}")
            return None, None, temp_demucs_segments_dir

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with demucs separation: {e}{Style.RESET_ALL}")
        return None, None, temp_demucs_segments_dir
    except Exception as e:
        print(f"{Fore.RED}Unexpected error with demucs separation: {e}{Style.RESET_ALL}")
        return None, None, temp_demucs_segments_dir

    return demucs_vocal_wav_path, demucs_instrumental_wav_path, temp_demucs_segments_dir