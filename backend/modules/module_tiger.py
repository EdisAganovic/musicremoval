"""
MODULE: module_tiger.py - TIGER-DnR CINEMATIC 3-STEM SEPARATION ENGINE

ROLE: Specialized Neural Audio Separation for Cinema, Anime, and Cartoons.
      Extracts Dialogue, Sound Effects (SFX/Foley), and Music using LiteRT / TFLite.
      Combines Dialogue + SFX into a clean 'No Music' stem preserving 100% of cartoon Foley.
"""
import os
import sys
import time
import tempfile
import numpy as np
import soundfile as sf
import torch
from colorama import Fore, Style
from tqdm import tqdm
from module_ffmpeg import get_audio_duration, FFMPEG_EXE

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        from tensorflow.lite.python.interpreter import Interpreter
    except ImportError:
        Interpreter = None

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pretrained_models", "tiger_dnr"))
MODEL_URL = "https://huggingface.co/litert-community/TIGER-DnR-LiteRT/resolve/main/tiger_dialog_fp16.tflite"
MODEL_FILENAME = "tiger_dialog_fp16.tflite"


def ensure_tiger_model_downloaded() -> str:
    """Ensures the TIGER-DnR LiteRT model is downloaded to disk."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    dest_path = os.path.join(MODEL_DIR, MODEL_FILENAME)
    if not os.path.exists(dest_path) or os.path.getsize(dest_path) < 1000000:
        print(f"\n{Fore.CYAN}Downloading TIGER-DnR model from Hugging Face (16 MB)...{Style.RESET_ALL}")
        import urllib.request
        urllib.request.urlretrieve(MODEL_URL, dest_path)
        print(f"{Fore.GREEN}[OK] Downloaded TIGER-DnR model ({os.path.getsize(dest_path) / (1024*1024):.1f} MB){Style.RESET_ALL}\n")
    return dest_path


def separate_with_tiger(
    temp_audio_wav_path: str,
    output_base_dir: str,
    base_audio_name_no_ext: str,
    want_instrumental: bool = False
):
    """
    Separates Dialogue, Sound Effects (SFX), and Music from cinematic audio using TIGER-DnR.

    Args:
        temp_audio_wav_path: Path to input WAV.
        output_base_dir: Directory for output stems.
        base_audio_name_no_ext: Base name for file naming.
        want_instrumental: If True, also outputs background music score.

    Returns:
        tuple: (dialogue_sfx_path, music_path, temp_tiger_dir)
    """
    print(f"\n{Fore.CYAN}--- Separating with TIGER-DnR (Cinematic Dialogue + SFX Engine) ---{Style.RESET_ALL}")
    os.makedirs(output_base_dir, exist_ok=True)
    model_path = ensure_tiger_model_downloaded()

    if Interpreter is None:
        raise RuntimeError("ai-edge-litert is not installed. Please run 'uv pip install ai-edge-litert'.")

    # Load audio
    wav_data, orig_sr = sf.read(temp_audio_wav_path, dtype='float32')
    total_duration = len(wav_data) / orig_sr
    print(f"Loaded audio: {total_duration:.2f}s, original sample rate: {orig_sr} Hz")

    # Resample to 44.1 kHz mono if needed (TIGER requires 44.1kHz mono)
    TARGET_SR = 44100
    temp_tiger_dir = tempfile.mkdtemp(dir="_temp")
    
    if orig_sr != TARGET_SR or (wav_data.ndim > 1 and wav_data.shape[1] > 1):
        if wav_data.ndim > 1:
            wav_mono = np.mean(wav_data, axis=1)
        else:
            wav_mono = wav_data

        if orig_sr != TARGET_SR:
            import resampy
            wav_44k = resampy.resample(wav_mono, orig_sr, TARGET_SR)
        else:
            wav_44k = wav_mono
    else:
        wav_44k = wav_data if wav_data.ndim == 1 else wav_data[:, 0]

    SR, WIN, HOP, T = TARGET_SR, 2048, 512, 1040
    CHUNK_LEN = (T - 1) * HOP  # 531968 samples = 12.06s
    HOP_LEN = CHUNK_LEN // 2   # 50% overlap for smooth reconstruction

    num_samples = len(wav_44k)
    out_dialogue = np.zeros(num_samples + CHUNK_LEN, dtype=np.float32)
    out_effects = np.zeros(num_samples + CHUNK_LEN, dtype=np.float32)
    out_music = np.zeros(num_samples + CHUNK_LEN, dtype=np.float32)
    weight = np.zeros(num_samples + CHUNK_LEN, dtype=np.float32)
    window_weight = np.hanning(CHUNK_LEN).astype(np.float32)

    # Initialize TFLite interpreter
    it = Interpreter(model_path=model_path, num_threads=8)
    it.allocate_tensors()
    in_idx = it.get_input_details()[0]['index']
    out_details = sorted(it.get_output_details(), key=lambda o: o['index'])
    hann_win = torch.hann_window(WIN)

    # Step through chunks with progress bar
    starts = list(range(0, num_samples, HOP_LEN))
    for start in tqdm(starts, desc="TIGER-DnR Overlap-Add", unit="chunk"):
        end = start + CHUNK_LEN
        chunk = np.zeros(CHUNK_LEN, dtype=np.float32)
        valid_len = min(num_samples - start, CHUNK_LEN)
        if valid_len <= 0:
            break
        chunk[:valid_len] = wav_44k[start:start+valid_len]

        # Reflect pad 1024 samples on both sides (torch.stft center=True equivalent)
        padded_chunk = np.concatenate([chunk[WIN//2:0:-1], chunk, chunk[-2:-WIN//2-2:-1]])

        it.set_tensor(in_idx, padded_chunk[None])
        it.invoke()

        real = it.get_tensor(out_details[0]['index'])
        imag = it.get_tensor(out_details[1]['index'])

        spec = torch.complex(torch.tensor(real), torch.tensor(imag))[0]

        # source 2 = dialogue, source 1 = sound effects, source 0 = music
        d_chunk = torch.istft(spec[2], n_fft=WIN, hop_length=HOP, window=hann_win, length=CHUNK_LEN).numpy()
        e_chunk = torch.istft(spec[1], n_fft=WIN, hop_length=HOP, window=hann_win, length=CHUNK_LEN).numpy()
        m_chunk = torch.istft(spec[0], n_fft=WIN, hop_length=HOP, window=hann_win, length=CHUNK_LEN).numpy()

        out_dialogue[start:end] += d_chunk * window_weight
        out_effects[start:end] += e_chunk * window_weight
        out_music[start:end] += m_chunk * window_weight
        weight[start:end] += window_weight

    # Normalize weights
    mask = weight > 1e-4
    out_dialogue[mask] /= weight[mask]
    out_effects[mask] /= weight[mask]
    out_music[mask] /= weight[mask]

    out_dialogue = out_dialogue[:num_samples]
    out_effects = out_effects[:num_samples]
    out_music = out_music[:num_samples]

    # Combine Dialogue + Sound Effects (the clean no-music track)
    no_music_dialogue_sfx = (out_dialogue + out_effects)

    # Resample back to original SR if needed
    if orig_sr != TARGET_SR:
        import resampy
        no_music_dialogue_sfx = resampy.resample(no_music_dialogue_sfx, TARGET_SR, orig_sr)
        if want_instrumental:
            out_music = resampy.resample(out_music, TARGET_SR, orig_sr)

    # Save output stems
    dialogue_sfx_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_dialogue_sfx.wav")
    sf.write(dialogue_sfx_path, no_music_dialogue_sfx, orig_sr)

    music_path = None
    if want_instrumental:
        music_path = os.path.join(temp_tiger_dir, f"{base_audio_name_no_ext}_tiger_music.wav")
        sf.write(music_path, out_music, orig_sr)

    print(f"\n{Fore.GREEN}[OK] TIGER-DnR separated {total_duration:.2f}s audio successfully.{Style.RESET_ALL}")
    return dialogue_sfx_path, music_path, temp_tiger_dir
