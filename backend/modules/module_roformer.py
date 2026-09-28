"""
MODULE: module_roformer.py - MEL-BAND ROFORMER & MDX23C BGM SEPARATION ENGINE

ROLE: Specialized Background Music (BGM) separation for Movies, Anime, and Cartoons.
      Extracts background music scores while preserving dialogue, speech,
      screaming, Foley, and cartoon sound effects (SFX) intact in the primary output stem.
      Supports target CUDA device allocation (multi-GPU) and configurable batch size scaling.
"""
import os
import sys
import tempfile
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, split_audio_into_segments

try:
    from core.constants import DEFAULT_ROFORMER_MODEL, DEFAULT_ROFORMER_BATCH_SIZE
except ImportError:
    from backend.core.constants import DEFAULT_ROFORMER_MODEL, DEFAULT_ROFORMER_BATCH_SIZE

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
    progress_callback: callable = None,
    device_str: str = None,
    roformer_batch_size: int = DEFAULT_ROFORMER_BATCH_SIZE
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
        device_str: Target CUDA device (e.g. 'cuda:0', 'cuda:1').
        roformer_batch_size: Parallel chunk batch size (default 4 for accelerated throughput).

    Returns:
        tuple: (path_to_dialogue_sfx_wav, path_to_music_instrumental_wav_or_None, temp_segments_dir)
    """
    if device_str is None:
        device_str = "cuda:0" if torch.cuda.is_available() else "cpu"

    effective_batch_size = max(1, int(roformer_batch_size or 4))
    print(f"\n{Fore.CYAN}--- Separating with Mel-Band Roformer BGM Model: {model_filename} on {device_str} (Batch Size: {effective_batch_size}) ---{Style.RESET_ALL}")
    os.makedirs(output_base_dir, exist_ok=True)
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    if progress_callback:
        progress_callback("Initializing Roformer BGM Engine", 20)

    use_native_fp16 = False
    try:
        import torch
        use_native_fp16 = torch.cuda.is_available()
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

    temp_segments_dir = None
    if pre_split_segments:
        split_audio_paths = pre_split_segments
        temp_segments_dir = tempfile.mkdtemp(dir="_temp")
    else:
        split_audio_paths = None

    def process_single_file(input_wav: str, out_dir: str, cb=None, start_p=20, end_p=85, label="Roformer", target_device="cuda:0"):
        """Runs separator on a single WAV file, returning (dialogue_sfx_path, music_path)."""
        separator = Separator(
            output_dir=out_dir,
            output_format="WAV",
            model_file_dir=MODEL_CACHE_DIR,
            use_native_fp16=use_native_fp16,
            mdx_params={'hop_length': 1024, 'segment_size': 256, 'overlap': 0.25, 'batch_size': effective_batch_size, 'enable_denoise': False},
            mdx23c_params={'batch_size': effective_batch_size, 'overlap': 8},
            roformer_params={'batch_size': effective_batch_size, 'overlap': 8},
        )

        # Configure specific CUDA device
        if "cuda" in target_device and torch.cuda.is_available():
            try:
                import torch
                dev_obj = torch.device(target_device)
                dev_idx = dev_obj.index if dev_obj.index is not None else 0
                separator.torch_device = dev_obj
                separator.onnx_execution_provider = [
                    ("CUDAExecutionProvider", {"device_id": dev_idx}),
                    "CPUExecutionProvider"
                ]
            except Exception:
                pass

        if cb:
            cb(f"{label}: Loading Model", start_p)
        separator.load_model(model_filename=model_filename)

        with TqdmProgressHook(cb, start_pct=start_p, end_pct=end_p, desc_prefix=label):
            separated_files = separator.separate(input_wav)

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

    # Single file processing
    vocal_sfx_p, music_p = process_single_file(
        temp_audio_wav_path, output_base_dir,
        cb=progress_callback,
        start_p=20, end_p=85,
        label="Roformer BGM",
        target_device=device_str
    )
    return vocal_sfx_p, (music_p if want_instrumental else None), None
