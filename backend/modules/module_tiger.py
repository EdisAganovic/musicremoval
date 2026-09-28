"""
MODULE: module_tiger.py - OPTIMIZED MULTI-GPU PYTORCH CUDA TIGER-DnR ENGINE

ROLE: Accelerated Native PyTorch CUDA 3-Stem Separation (Dialogue, SFX/Foley, Music).
      Supports Multi-GPU parallel passes, configurable batch scaling, and Tensor Core optimizations.
"""
import os
import sys
import time
import tempfile
import numpy as np
import soundfile as sf
import torch
import torchaudio.transforms as T
from colorama import Fore, Style

try:
    from modules.module_cuda import get_available_cuda_devices
except ImportError:
    from module_cuda import get_available_cuda_devices

try:
    from core.constants import DEFAULT_TIGER_TARGET, DEFAULT_TIGER_OVERLAP, DEFAULT_TIGER_BATCH_SIZE
except ImportError:
    from backend.core.constants import DEFAULT_TIGER_TARGET, DEFAULT_TIGER_OVERLAP, DEFAULT_TIGER_BATCH_SIZE

try:
    import look2hear.models
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import look2hear.models

MODEL_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pretrained_models", "tiger_dnr_torch"))
_TIGER_MODEL_INSTANCES = {}

# Enable Tensor Core matmul acceleration on Blackwell & Ampere architectures
if torch.cuda.is_available():
    try:
        torch.set_float32_matmul_precision('high')
        torch.backends.cudnn.benchmark = True
    except Exception:
        pass


def get_tiger_model(device_str: str = None):
    """Loads and caches the PyTorch TIGER-DnR model on specified CUDA device."""
    global _TIGER_MODEL_INSTANCES
    if device_str is None:
        device_str = "cuda:0" if torch.cuda.is_available() else "cpu"

    if device_str not in _TIGER_MODEL_INSTANCES:
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
        device = torch.device(device_str)
        dev_idx = device.index if device.index is not None else 0
        gpu_name = torch.cuda.get_device_name(dev_idx) if device.type == 'cuda' else 'CPU'
        print(f"\n{Fore.CYAN}Loading PyTorch TIGER-DnR model onto {device} ({gpu_name})...{Style.RESET_ALL}")
        model = look2hear.models.TIGERDNR.from_pretrained("JusperLee/TIGER-DnR", cache_dir=MODEL_CACHE_DIR)
        model = model.to(device)
        model.eval()
        _TIGER_MODEL_INSTANCES[device_str] = (model, device)
        print(f"{Fore.GREEN}[OK] PyTorch TIGER-DnR ready on {device}.{Style.RESET_ALL}\n")

    return _TIGER_MODEL_INSTANCES[device_str]


def separate_with_tiger(
    temp_audio_wav_path: str,
    output_base_dir: str,
    base_audio_name_no_ext: str,
    tiger_target: str = DEFAULT_TIGER_TARGET,
    tiger_overlap: int = DEFAULT_TIGER_OVERLAP,
    tiger_batch_size: int = DEFAULT_TIGER_BATCH_SIZE,
    progress_callback = None,
    want_instrumental: bool = False,
    device_str: str = None
):
    """
    Separates Dialogue, Sound Effects (SFX), and Music using Tensor Core accelerated PyTorch CUDA.
    Supports Dual-GPU execution and configurable sliding-window batch sizes (e.g. 4, 8, 12).

    Args:
        temp_audio_wav_path: Path to input WAV.
        output_base_dir: Directory for output stems.
        base_audio_name_no_ext: Base name for file naming.
        tiger_target: "dialogue_sfx" (default), "dialogue", "sfx", "music".
        tiger_overlap: Overlap percentage (50 or 75 for high precision).
        tiger_batch_size: Parallel chunk batch size (default 8 for 16GB/10GB VRAM).
        progress_callback: Optional progress reporter callback(step_name, progress_pct).
        want_instrumental: If True, also exports background music.
        device_str: Specific device target (e.g. 'cuda:0', 'cuda:1'). Defaults to primary.

    Returns:
        tuple: (target_output_path, music_path, temp_tiger_dir)
    """
    if device_str is None:
        device_str = "cuda:0" if torch.cuda.is_available() else "cpu"

    effective_batch_size = max(1, int(tiger_batch_size or 8))
    print(f"\n{Fore.CYAN}--- Separating with High-Speed PyTorch CUDA TIGER-DnR Engine on {device_str} ---{Style.RESET_ALL}")
    print(f"Target Stem Mode: {tiger_target.upper()} | Overlap Window: {tiger_overlap}% | Batch Size: {effective_batch_size}")
    os.makedirs(output_base_dir, exist_ok=True)
    temp_tiger_dir = tempfile.mkdtemp(dir="_temp")

    model, device = get_tiger_model(device_str)

    # Load audio using soundfile
    data, orig_sr = sf.read(temp_audio_wav_path, dtype='float32')
    total_duration = len(data) / orig_sr
    print(f"Loaded audio: {total_duration:.2f}s, sample rate: {orig_sr} Hz on {device}")

    # TIGER expects 44.1 kHz mono
    TARGET_SR = 44100
    if data.ndim > 1:
        mono_data = np.mean(data, axis=1)
    else:
        mono_data = data

    # Fast GPU-accelerated tensor resampling via torchaudio
    wav_tensor_raw = torch.from_numpy(mono_data).float().unsqueeze(0).to(device)
    if orig_sr != TARGET_SR:
        resampler_in = T.Resample(orig_freq=orig_sr, new_freq=TARGET_SR).to(device)
        wav_44k_tensor = resampler_in(wav_tensor_raw)
    else:
        wav_44k_tensor = wav_tensor_raw

    # Input tensor shape: [1, 1, samples]
    wav_tensor = wav_44k_tensor.unsqueeze(0)

    # Calculate hop duration based on overlap percentage
    TARGET_LEN = 12.0
    if tiger_overlap >= 75:
        HOP_SEC = 3.0   # 75% overlap
    else:
        HOP_SEC = 6.0   # 50% overlap

    BATCH_SIZE = effective_batch_size if device.type == 'cuda' else 1

    t_start = time.time()
    with torch.inference_mode():
        with torch.autocast('cuda', dtype=torch.float16, enabled=(device.type == 'cuda')):
            d_out, e_out, m_out = model(
                wav_tensor,
                target_length=TARGET_LEN,
                hop_length=HOP_SEC,
                batch_size=BATCH_SIZE,
                progress_callback=progress_callback,
                want_instrumental=want_instrumental,
                target_stem=tiger_target
            )

    d_tensor = d_out.squeeze() if d_out is not None else None
    e_tensor = e_out.squeeze() if e_out is not None else None
    m_tensor = m_out.squeeze() if m_out is not None else None

    t_end = time.time()
    infer_time = t_end - t_start
    print(f"\n{Fore.GREEN}Neural inference completed in {infer_time:.2f}s ({total_duration / max(infer_time, 0.01):.1f}x realtime on {device}).{Style.RESET_ALL}")

    # Select target stem on GPU tensor
    if tiger_target == "dialogue":
        target_tensor = d_tensor
    elif tiger_target == "sfx":
        target_tensor = e_tensor
    elif tiger_target == "music":
        target_tensor = m_tensor
    else:  # "dialogue_sfx" (default)
        if d_tensor is not None and e_tensor is not None:
            target_tensor = d_tensor + e_tensor
        elif d_tensor is not None:
            target_tensor = d_tensor
        elif e_tensor is not None:
            target_tensor = e_tensor
        else:
            target_tensor = m_tensor

    # Resample back to original sample rate on GPU if needed
    if orig_sr != TARGET_SR:
        resampler_out = T.Resample(orig_freq=TARGET_SR, new_freq=orig_sr).to(device)
        if target_tensor is not None:
            target_tensor = resampler_out(target_tensor.unsqueeze(0)).squeeze(0)
        if want_instrumental and m_tensor is not None:
            m_tensor = resampler_out(m_tensor.unsqueeze(0)).squeeze(0)

    target_audio = target_tensor.to(torch.float32).cpu().numpy() if target_tensor is not None else None
    music_audio = m_tensor.to(torch.float32).cpu().numpy() if (want_instrumental and m_tensor is not None) else None

    # Save output stems
    target_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_{tiger_target}.wav")
    sf.write(target_path, target_audio, orig_sr)

    music_path = None
    if want_instrumental and music_audio is not None:
        music_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_music.wav")
        sf.write(music_path, music_audio, orig_sr)

    print(f"{Fore.GREEN}[OK] PyTorch CUDA TIGER-DnR separated {total_duration:.2f}s audio successfully on {device}.{Style.RESET_ALL}")
    return target_path, music_path, temp_tiger_dir
