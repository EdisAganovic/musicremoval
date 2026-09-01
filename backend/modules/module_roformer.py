"""
MODULE: module_roformer.py - MEL-BAND ROFORMER & MDX23C BGM SEPARATION ENGINE

ROLE: Specialized Background Music (BGM) separation for Movies, Anime, and Cartoons.
      Extracts background music scores while preserving dialogue, speech,
      screaming, Foley, and cartoon sound effects (SFX) intact in the primary output stem.
"""
import os
import sys
import tempfile
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, split_audio_into_segments
from core.constants import DEFAULT_ROFORMER_MODEL

try:
    from services.process_manager import tracked_run
except ImportError:
    import subprocess
    tracked_run = subprocess.run

# Directory to cache downloaded model weights
MODEL_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pretrained_models", "audio_separator_models"))
DEFAULT_BGM_MODEL = DEFAULT_ROFORMER_MODEL


class TqdmProgressHook:
    """Intercepts tqdm updates from audio_separator and maps progress to the task progress_callback."""
    def __init__(self, callback, start_pct=20, end_pct=85, desc_prefix="Roformer"):
        self.callback = callback
        self.start_pct = start_pct
        self.end_pct = end_pct
        self.desc_prefix = desc_prefix
        self.original_update = tqdm.update

    def __enter__(self):
        callback = self.callback
        start_pct = self.start_pct
        end_pct = self.end_pct
        desc_prefix = self.desc_prefix
        orig_update = self.original_update

        def hooked_update(pbar_self, n=1):
            res = orig_update(pbar_self, n)
            try:
                if callback and getattr(pbar_self, "total", None) and pbar_self.total > 0:
                    fraction = min(1.0, max(0.0, pbar_self.n / pbar_self.total))
                    pct = int(fraction * 100)
                    overall_progress = int(start_pct + fraction * (end_pct - start_pct))
                    callback(f"{desc_prefix} ({pct}%)", overall_progress)
            except Exception:
                pass
            return res

        tqdm.update = hooked_update
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        tqdm.update = self.original_update


def separate_with_roformer(
    temp_audio_wav_path: str,
    output_base_dir: str,
    base_audio_name_no_ext: str,
    model_filename: str = DEFAULT_BGM_MODEL,
    pre_split_segments: list = None,
    want_instrumental: bool = False,
    progress_callback: callable = None
):
    """
    Separates background music from dialogue & SFX using audio-separator with Mel-Band Roformer BGM / MDX models.

    Args:
        temp_audio_wav_path: Path to the source WAV file.
        output_base_dir: Directory where outputs are saved.
        base_audio_name_no_ext: Base name for files.
        model_filename: Model checkpoint filename (e.g. 'mel_band_roformer_bgm_crowd.ckpt').
        pre_split_segments: Optional list of pre-split audio segments.
        want_instrumental: If True, returns (vocal_or_dialogue_sfx_path, music_instrumental_path).
        progress_callback: Optional callback fn(step_str, progress_int) to report real-time percentage.

    Returns:
        tuple: (path_to_dialogue_sfx_wav, path_to_music_instrumental_wav_or_None, temp_segments_dir)
    """
    print(f"\n{Fore.CYAN}--- Separating with Mel-Band Roformer BGM Model: {model_filename} ---{Style.RESET_ALL}")
    os.makedirs(output_base_dir, exist_ok=True)
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    if progress_callback:
        progress_callback("Initializing Roformer BGM Engine", 20)

    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.exists(torch_lib):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(torch_lib)
            if torch_lib not in os.environ.get("PATH", ""):
                os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

    try:
        from audio_separator.separator import Separator
    except ImportError:
        print(f"{Fore.RED}Error: audio-separator package is not installed.{Style.RESET_ALL}")
        raise RuntimeError("audio-separator package is required for Roformer BGM model.")

    audio_duration = get_audio_duration(temp_audio_wav_path)
    if audio_duration is None:
        print(f"{Fore.RED}Failed to determine audio duration for Roformer separation.{Style.RESET_ALL}")
        return None, None, None

    SEGMENT_DURATION_SECONDS = 600  # 10 minute chunks for optimal VRAM efficiency
    temp_segments_dir = None

    if pre_split_segments:
        split_audio_paths = pre_split_segments
        temp_segments_dir = tempfile.mkdtemp(dir="_temp")
    elif audio_duration > SEGMENT_DURATION_SECONDS:
        print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting for Roformer BGM...{Style.RESET_ALL}\n")
        temp_segments_dir, split_audio_paths = split_audio_into_segments(
            temp_audio_wav_path, audio_duration, SEGMENT_DURATION_SECONDS
        )
        print(f"\n{Fore.GREEN}[OK] Audio split into {len(split_audio_paths)} segments for Roformer.{Style.RESET_ALL}")
    else:
        split_audio_paths = None

    def process_single_file(input_wav: str, out_dir: str, cb=None, start_p=20, end_p=85, label="Roformer"):
        """Runs separator on a single WAV file, returning (dialogue_sfx_path, music_path)."""
        separator = Separator(
            output_dir=out_dir,
            output_format="WAV",
            model_file_dir=MODEL_CACHE_DIR
        )
        if cb:
            cb(f"{label}: Loading Model", start_p)
        separator.load_model(model_filename=model_filename)

        with TqdmProgressHook(cb, start_pct=start_p, end_pct=end_p, desc_prefix=label):
            separated_files = separator.separate(input_wav)

        # audio-separator returns list of generated filenames in out_dir
        # BGM models produce two stems:
        # 1. Background Music / Instrumental (music score to remove)
        # 2. Vocals / No_BGM / Speech+SFX (dialogue + effects to keep)
        dialogue_sfx_path = None
        music_path = None

        for fname in separated_files:
            full_p = os.path.join(out_dir, fname) if not os.path.isabs(fname) else fname
            fname_lower = fname.lower()
            if any(tag in fname_lower for tag in ["_(crowd)_", "(crowd)", "_(vocals)_", "(vocals)", "_(speech)_", "_(no_bgm)_", "_(lead)_"]):
                dialogue_sfx_path = full_p
            elif any(tag in fname_lower for tag in ["_(other)_", "(other)", "_(instrumental)_", "(instrumental)", "_(bgm)_", "_(music)_"]):
                music_path = full_p

        # Fallback if names are generic
        if not dialogue_sfx_path and len(separated_files) >= 1:
            dialogue_sfx_path = os.path.join(out_dir, separated_files[0]) if not os.path.isabs(separated_files[0]) else separated_files[0]
        if not music_path and len(separated_files) >= 2:
            music_path = os.path.join(out_dir, separated_files[1]) if not os.path.isabs(separated_files[1]) else separated_files[1]

        return dialogue_sfx_path, music_path

    # Multi-segment parallel processing
    if split_audio_paths:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_workers = min(3, len(split_audio_paths))
        print(f"\n{Fore.CYAN}[Roformer BGM] Launching {len(split_audio_paths)} segments in parallel ({max_workers} concurrent GPU workers on CUDA)...{Style.RESET_ALL}")

        completed_count = 0
        total_segs = len(split_audio_paths)

        def process_segment_task(item):
            nonlocal completed_count
            i, segment_path = item
            seg_out_dir = os.path.join(output_base_dir, f"seg_{i:03d}")
            os.makedirs(seg_out_dir, exist_ok=True)
            try:
                vocal_sfx_p, music_p = process_single_file(
                    segment_path, seg_out_dir,
                    cb=progress_callback,
                    start_p=int(20 + (i / total_segs) * 65),
                    end_p=int(20 + ((i + 1) / total_segs) * 65),
                    label=f"Roformer Seg {i+1}/{total_segs}"
                )
            except Exception as e:
                print(f"\n{Fore.RED}{'='*70}")
                print(f"[FATAL CHUNK ERROR] Roformer BGM failed on Segment {i+1}/{len(split_audio_paths)}")
                print(f"Segment Audio File: {segment_path}")
                print(f"Error Details: {e}")
                print(f"{'='*70}{Style.RESET_ALL}\n")
                raise RuntimeError(f"Roformer failed on segment {i+1} ({os.path.basename(segment_path)}): {e}")

            if not (vocal_sfx_p and os.path.exists(vocal_sfx_p) and os.path.getsize(vocal_sfx_p) > 1024):
                raise RuntimeError(f"Roformer produced empty output on segment {i+1} ({os.path.basename(segment_path)})")

            return i, vocal_sfx_p, music_p

        results = [None] * len(split_audio_paths)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_segment_task, (i, p)): (i, p) for i, p in enumerate(split_audio_paths)}
            with tqdm(total=len(split_audio_paths), desc="Roformer Parallel", unit="seg") as pbar:
                for future in as_completed(futures):
                    i, vocal_sfx_p, music_p = future.result()
                    results[i] = (vocal_sfx_p, music_p)
                    pbar.update(1)
                    completed_count += 1
                    if progress_callback:
                        progress_callback(f"Roformer Segments ({completed_count}/{total_segs})", int(20 + (completed_count / total_segs) * 65))

        vocal_paths = [r[0] for r in results if r and r[0]]
        music_paths = [r[1] for r in results if r and r[1]]

        # Concatenate vocal / dialogue+SFX segments
        concat_list_path = os.path.join(temp_segments_dir, "roformer_concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in vocal_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        final_dialogue_wav = os.path.join(temp_segments_dir, "concatenated_roformer_dialogue_sfx.wav")
        ffmpeg_concat_cmd = [FFMPEG_EXE, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", final_dialogue_wav]
        tracked_run(ffmpeg_concat_cmd, check=True)

        final_music_wav = None
        if want_instrumental and len(music_paths) == len(split_audio_paths):
            music_concat_list_path = os.path.join(temp_segments_dir, "roformer_concat_music_list.txt")
            with open(music_concat_list_path, "w", encoding="utf-8") as f:
                for p in music_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")
            final_music_wav = os.path.join(temp_segments_dir, "concatenated_roformer_music.wav")
            ffmpeg_music_concat = [FFMPEG_EXE, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", music_concat_list_path, "-c", "copy", final_music_wav]
            try:
                tracked_run(ffmpeg_music_concat, check=True)
            except Exception:
                final_music_wav = None

        print(f"\n{Fore.GREEN}[OK] All {len(vocal_paths)} Roformer BGM segments joined successfully.{Style.RESET_ALL}")
        return final_dialogue_wav, final_music_wav, temp_segments_dir

    else:
        # Single file processing
        vocal_sfx_p, music_p = process_single_file(
            temp_audio_wav_path, output_base_dir,
            cb=progress_callback,
            start_p=20, end_p=85,
            label="Roformer BGM"
        )
        return vocal_sfx_p, (music_p if want_instrumental else None), None
