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

try:
    from services.process_manager import tracked_run
except ImportError:
    import subprocess
    tracked_run = subprocess.run

# Directory to cache downloaded model weights
MODEL_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pretrained_models", "audio_separator_models"))
DEFAULT_BGM_MODEL = "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"


def separate_with_roformer(
    temp_audio_wav_path: str,
    output_base_dir: str,
    base_audio_name_no_ext: str,
    model_filename: str = DEFAULT_BGM_MODEL,
    pre_split_segments: list = None,
    want_instrumental: bool = False
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

    Returns:
        tuple: (path_to_dialogue_sfx_wav, path_to_music_instrumental_wav_or_None, temp_segments_dir)
    """
    print(f"\n{Fore.CYAN}--- Separating with Mel-Band Roformer BGM Model: {model_filename} ---{Style.RESET_ALL}")
    os.makedirs(output_base_dir, exist_ok=True)
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

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

    def process_single_file(input_wav: str, out_dir: str):
        """Runs separator on a single WAV file, returning (dialogue_sfx_path, music_path)."""
        separator = Separator(
            output_dir=out_dir,
            output_format="WAV",
            model_file_dir=MODEL_CACHE_DIR
        )
        separator.load_model(model_filename=model_filename)
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

    # Multi-segment processing
    if split_audio_paths:
        results = [None] * len(split_audio_paths)
        for i, segment_path in enumerate(tqdm(split_audio_paths, desc="Roformer BGM Segments", unit="seg")):
            seg_out_dir = os.path.join(output_base_dir, f"seg_{i:03d}")
            os.makedirs(seg_out_dir, exist_ok=True)
            
            try:
                vocal_sfx_p, music_p = process_single_file(segment_path, seg_out_dir)
            except Exception as e:
                print(f"\n{Fore.RED}{'='*70}")
                print(f"[FATAL CHUNK ERROR] Roformer BGM failed on Segment {i+1}/{len(split_audio_paths)}")
                print(f"Segment Audio File: {segment_path}")
                print(f"Error Details: {e}")
                print(f"{'='*70}{Style.RESET_ALL}\n")
                raise RuntimeError(f"Roformer failed on segment {i+1} ({os.path.basename(segment_path)}): {e}")

            if not (vocal_sfx_p and os.path.exists(vocal_sfx_p) and os.path.getsize(vocal_sfx_p) > 1024):
                raise RuntimeError(f"Roformer produced empty output on segment {i+1} ({os.path.basename(segment_path)})")

            results[i] = (vocal_sfx_p, music_p)

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
        # Single short file
        dialogue_sfx_path, music_path = process_single_file(temp_audio_wav_path, output_base_dir)
        return dialogue_sfx_path, (music_path if want_instrumental else None), None
