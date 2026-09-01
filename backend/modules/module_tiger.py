"""
MODULE: module_tiger.py - OPTIMIZED PYTORCH CUDA TIGER-DnR ENGINE

ROLE: Accelerated Native PyTorch CUDA 3-Stem Separation (Dialogue, SFX/Foley, Music).
      Uses Tensor Core FP16 execution, GPU sliding-window crossfading, and customizable stem targeting.
"""
import os
import sys
import time
import tempfile
import numpy as np
import soundfile as sf
import resampy
import torch
from colorama import Fore, Style

# Ensure look2hear can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import look2hear.models
from core.constants import DEFAULT_TIGER_TARGET, DEFAULT_TIGER_OVERLAP

MODEL_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pretrained_models", "tiger_dnr_torch"))
_TIGER_MODEL_INSTANCE = None
_TIGER_DEVICE = None


def get_tiger_model():
    """Loads and caches the PyTorch TIGER-DnR model on CUDA."""
    global _TIGER_MODEL_INSTANCE, _TIGER_DEVICE
    if _TIGER_MODEL_INSTANCE is None:
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"\n{Fore.CYAN}Loading PyTorch TIGER-DnR model onto {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})...{Style.RESET_ALL}")
        model = look2hear.models.TIGERDNR.from_pretrained("JusperLee/TIGER-DnR", cache_dir=MODEL_CACHE_DIR)
        model = model.to(device)
        model.eval()
        _TIGER_MODEL_INSTANCE = model
        _TIGER_DEVICE = device
        print(f"{Fore.GREEN}[OK] PyTorch TIGER-DnR ready on {device}.{Style.RESET_ALL}\n")
    return _TIGER_MODEL_INSTANCE, _TIGER_DEVICE


def separate_with_tiger(
    temp_audio_wav_path: str,
    output_base_dir: str,
    base_audio_name_no_ext: str,
    tiger_target: str = DEFAULT_TIGER_TARGET,
    tiger_overlap: int = DEFAULT_TIGER_OVERLAP,
    progress_callback = None,
    want_instrumental: bool = False
):
    """
    Separates Dialogue, Sound Effects (SFX), and Music using Tensor Core accelerated PyTorch CUDA.

    Args:
        temp_audio_wav_path: Path to input WAV.
        output_base_dir: Directory for output stems.
        base_audio_name_no_ext: Base name for file naming.
        tiger_target: "dialogue_sfx" (default), "dialogue", "sfx", "music".
        tiger_overlap: Overlap percentage (50 or 75 for high precision).
        progress_callback: Optional progress reporter callback(step_name, progress_pct).
        want_instrumental: If True, also exports background music.

    Returns:
        tuple: (target_output_path, music_path, temp_tiger_dir)
    """
    print(f"\n{Fore.CYAN}--- Separating with High-Speed PyTorch CUDA TIGER-DnR Engine ---{Style.RESET_ALL}")
    print(f"Target Stem Mode: {tiger_target.upper()} | Overlap Window: {tiger_overlap}%")
    os.makedirs(output_base_dir, exist_ok=True)
    temp_tiger_dir = tempfile.mkdtemp(dir="_temp")

    model, device = get_tiger_model()

    # Load audio using soundfile
    data, orig_sr = sf.read(temp_audio_wav_path, dtype='float32')
    total_duration = len(data) / orig_sr
    print(f"Loaded audio: {total_duration:.2f}s, sample rate: {orig_sr} Hz")

    # TIGER expects 44.1 kHz mono
    TARGET_SR = 44100
    if data.ndim > 1:
        mono_data = np.mean(data, axis=1)
    else:
        mono_data = data

    if orig_sr != TARGET_SR:
        wav_44k_np = resampy.resample(mono_data, orig_sr, TARGET_SR)
    else:
        wav_44k_np = mono_data

    # Input tensor shape: [1, 1, samples]
    wav_tensor = torch.from_numpy(wav_44k_np).unsqueeze(0).unsqueeze(0).to(device)

    # Calculate hop duration based on overlap percentage
    TARGET_LEN = 12.0
    if tiger_overlap >= 75:
        HOP_SEC = 3.0   # 75% overlap (4-pass Hann crossfade for classical / complex score preservation)
    else:
        HOP_SEC = 6.0   # 50% overlap (standard 2-pass high speed)

    BATCH_SIZE = 4 if device.type == 'cuda' else 1

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

    d_np = d_out.squeeze().to(torch.float32).cpu().numpy() if d_out is not None else None
    e_np = e_out.squeeze().to(torch.float32).cpu().numpy() if e_out is not None else None
    m_np = m_out.squeeze().to(torch.float32).cpu().numpy() if m_out is not None else None

    t_end = time.time()
    infer_time = t_end - t_start
    print(f"\n{Fore.GREEN}Neural inference completed in {infer_time:.2f}s ({total_duration / max(infer_time, 0.01):.1f}x realtime).{Style.RESET_ALL}")

    # Select target stem
    if tiger_target == "dialogue":
        target_audio = d_np
    elif tiger_target == "sfx":
        target_audio = e_np
    elif tiger_target == "music":
        target_audio = m_np
    else:  # "dialogue_sfx" (default)
        if d_np is not None and e_np is not None:
            target_audio = d_np + e_np
        elif d_np is not None:
            target_audio = d_np
        elif e_np is not None:
            target_audio = e_np
        else:
            target_audio = m_np

    # Resample back to original sample rate if needed
    if orig_sr != TARGET_SR:
        target_audio = resampy.resample(target_audio, TARGET_SR, orig_sr)
        if want_instrumental:
            m_np = resampy.resample(m_np, TARGET_SR, orig_sr)

    # Save output stems
    target_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_{tiger_target}.wav")
    sf.write(target_path, target_audio, orig_sr)

    music_path = None
    if want_instrumental:
        music_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_music.wav")
        sf.write(music_path, m_np, orig_sr)

    print(f"{Fore.GREEN}[OK] PyTorch CUDA TIGER-DnR separated {total_duration:.2f}s audio successfully on {device}.{Style.RESET_ALL}")
    return target_path, music_path, temp_tiger_dir
