"""
MODULE: module_audio.py - AUDIO ALIGNMENT AND MIXING

ROLE: Aligns and combines vocal tracks from multiple AI models

RESPONSIBILITIES:
  - Detects millisecond-level offsets via cross-correlation
  - Pads earlier track to synchronize both outputs
  - Mixes aligned tracks with configurable volume weights
  - Handles sample rate conversion and mono/stereo normalization

KEY FUNCTIONS:
  calculate_audio_lag(audio1, sr1, audio2, sr2, max_delay_seconds) → tuple
    - Returns: (delay_samples, delay_ms)
    - Uses FFT-based cross-correlation on audio envelopes
    - Positive lag means audio1 is delayed (audio2 starts earlier)
  
  align_audio_tracks(track1_path, track2_path, output1_path, output2_path) → tuple
    - Returns: (aligned_track1_path, aligned_track2_path)
    - Pads beginning of earlier track, ensures equal length
    - Falls back gracefully if numpy/scipy unavailable
  
  mix_audio_tracks(track1_path, track2_path, output_path, volume1, volume2) → str | None
    - Returns: path to mixed output file
    - Applies volume scaling, adds signals, normalizes if clipping

ALGORITHM:
  1. Convert to mono envelopes (50ms window average)
  2. FFT-based cross-correlation
  3. Find peak in correlation window (±2 seconds)
  4. Validate peak strength (>2x mean correlation)
  5. Pad earlier track with zeros at beginning
  6. Ensure both tracks have equal length

DEPENDENCIES:
  - numpy: Array operations, correlation
  - scipy.signal: Resampling, correlation
  - soundfile: Audio read/write
  - module_ffmpeg: FFMPEG_EXE for fallback operations
"""
import numpy as np
from scipy import signal
import soundfile as sf
from colorama import Fore, Style


def calculate_audio_lag(audio1, sr1, audio2, sr2, max_delay_seconds=2.0):
    """
    Calculates the lag between two audio signals.
    Positive result means audio1 is delayed relative to audio2 (audio2 starts earlier).
    """
    # Standardize sample rates for correlation
    if sr1 != sr2:
        if sr1 < sr2:
            num = int(audio2.shape[0] * sr1 / sr2)
            audio2 = signal.resample(audio2, num)
            sr2 = sr1
        else:
            num = int(audio1.shape[0] * sr2 / sr1)
            audio1 = signal.resample(audio1, num)
            sr1 = sr2
            
    # Prepare envelopes for more robust correlation
    def get_envelope(audio, sr):
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        envelope = np.abs(audio)
        win_size = int(sr * 0.05)
        if win_size > 1:
            envelope = np.convolve(envelope, np.ones(win_size)/win_size, mode='same')
        envelope = envelope - np.mean(envelope)
        std = np.std(envelope)
        if std > 0:
            envelope = envelope / std
        return envelope

    limit_samples = int(sr1 * 120)
    env1 = get_envelope(audio1[:limit_samples], sr1)
    env2 = get_envelope(audio2[:limit_samples], sr1)

    correlation = signal.correlate(env1, env2, mode='full', method='fft')
    center_idx = len(env2) - 1
    
    search_half_width = int(sr1 * max_delay_seconds)
    search_start = max(0, center_idx - search_half_width)
    search_end = min(len(correlation), center_idx + search_half_width + 1)
    
    windowed_corr = correlation[search_start:search_end]
    peak_idx_in_window = np.argmax(windowed_corr)
    peak_idx = search_start + peak_idx_in_window
    
    delay_samples = peak_idx - center_idx
    
    # Sanity check
    corr_max = windowed_corr[peak_idx_in_window]
    corr_mean = np.mean(np.abs(windowed_corr))
    if corr_max < 2.0 * corr_mean:
        return 0, 0
        
    delay_ms = (delay_samples / sr1) * 1000
    return delay_samples, delay_ms

def align_audio_tracks(track1_path, track2_path, output_aligned_track1_path, output_aligned_track2_path):
    """
    Aligns two audio tracks using FFT-based cross-correlation.
    Pads the beginning of the track that starts earlier.
    Saves the aligned tracks to new paths.

    Returns the paths to the aligned tracks, or None if alignment fails.
    """
    # Check for dependencies once at the start of the function
    try:
        import numpy as np
        from scipy import signal
        import soundfile as sf
        NUMPY_SCIPY_AVAILABLE = True
    except ImportError:
        NUMPY_SCIPY_AVAILABLE = False

    if not NUMPY_SCIPY_AVAILABLE:
        print(f"{Fore.RED}Cannot align audio tracks: numpy, scipy, or soundfile not available.{Style.RESET_ALL}")
        return track1_path, track2_path

    print(f"\n{Fore.CYAN}Attempting to align audio tracks using FFT cross-correlation...{Style.RESET_ALL}")
    try:
        audio1, sr1 = sf.read(track1_path)
        audio2, sr2 = sf.read(track2_path)

        delay_samples, delay_ms = calculate_audio_lag(audio1, sr1, audio2, sr2)
        
        if delay_ms == 0:
            print(f"{Fore.YELLOW}Warning: Weak correlation or no delay detected.{Style.RESET_ALL}")
        else:
            print(f"{Fore.BLUE}Calculated audio delay: {delay_ms:.2f} ms ({delay_samples} samples){Style.RESET_ALL}")

        aligned_audio1 = audio1
        aligned_audio2 = audio2

        if delay_samples > 0:
            # audio1 is delayed, so we pad audio2 at the beginning
            print(f"{Fore.BLUE}Padding Track 2 by {delay_ms:.2f} ms at the beginning.{Style.RESET_ALL}")
            # Pad beginning of audio2
            if audio2.ndim > 1:
                aligned_audio2 = np.pad(audio2, ((delay_samples, 0), (0, 0)), 'constant')
            else:
                aligned_audio2 = np.pad(audio2, (delay_samples, 0), 'constant')
            
            # Ensure both are same length at end
            diff = len(aligned_audio2) - len(audio1)
            if diff > 0:
                if audio1.ndim > 1:
                    aligned_audio1 = np.pad(audio1, ((0, diff), (0, 0)), 'constant')
                else:
                    aligned_audio1 = np.pad(audio1, (0, diff), 'constant')
            elif diff < 0:
                if audio2.ndim > 1:
                    aligned_audio2 = np.pad(aligned_audio2, ((0, -diff), (0, 0)), 'constant')
                else:
                    aligned_audio2 = np.pad(aligned_audio2, (0, -diff), 'constant')

        elif delay_samples < 0:
            # audio2 is delayed, so we pad audio1 at the beginning
            print(f"{Fore.BLUE}Padding Track 1 by {-delay_ms:.2f} ms at the beginning.{Style.RESET_ALL}")
            # Pad beginning of audio1
            if audio1.ndim > 1:
                aligned_audio1 = np.pad(audio1, ((-delay_samples, 0), (0, 0)), 'constant')
            else:
                aligned_audio1 = np.pad(audio1, (-delay_samples, 0), 'constant')
            
            # Ensure both are same length at end
            diff = len(aligned_audio1) - len(audio2)
            if diff > 0:
                if audio2.ndim > 1:
                    aligned_audio2 = np.pad(audio2, ((0, diff), (0, 0)), 'constant')
                else:
                    aligned_audio2 = np.pad(audio2, (0, diff), 'constant')
            elif diff < 0:
                if audio1.ndim > 1:
                    aligned_audio1 = np.pad(aligned_audio1, ((0, -diff), (0, 0)), 'constant')
                else:
                    aligned_audio1 = np.pad(aligned_audio1, (0, -diff), 'constant')
        else:
            print(f"{Fore.GREEN}Tracks are already aligned. No padding needed.{Style.RESET_ALL}")
            len1 = len(audio1)
            len2 = len(audio2)
            max_len = max(len1, len2)
            if audio1.ndim > 1:
                aligned_audio1 = np.pad(audio1, ((0, max_len - len1), (0, 0)), 'constant')
            else:
                aligned_audio1 = np.pad(audio1, (0, max_len - len1), 'constant')
            if audio2.ndim > 1:
                aligned_audio2 = np.pad(audio2, ((0, max_len - len2), (0, 0)), 'constant')
            else:
                aligned_audio2 = np.pad(audio2, (0, max_len - len2), 'constant')

        sf.write(output_aligned_track1_path, aligned_audio1, sr1)
        sf.write(output_aligned_track2_path, aligned_audio2, sr2)

        print(f"{Fore.GREEN}\N{check mark} Audio tracks aligned and saved.{Style.RESET_ALL}")
        return output_aligned_track1_path, output_aligned_track2_path

    except FileNotFoundError:
        print(f"{Fore.RED}Error: One of the audio files for alignment was not found.{Style.RESET_ALL}")
        return None, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"{Fore.RED}An error occurred during audio alignment: {e}{Style.RESET_ALL}")
        return None, None


def mix_audio_tracks(track1_path, track2_path, output_mixed_path, volume1=0.5, volume2=0.5):
    """
    Mixes two audio tracks together after aligning them.
    
    Args:
        track1_path: Path to the first audio track (typically Spleeter output)
        track2_path: Path to the second audio track (typically Demucs output)
        output_mixed_path: Path where the mixed output will be saved
        volume1: Volume level for the first track (0.0 to 1.0)
        volume2: Volume level for the second track (0.0 to 1.0)
    
    Returns:
        Path to the mixed output file, or None if mixing fails
    """
    try:
        import numpy as np
        from scipy import signal
        import soundfile as sf
        NUMPY_SCIPY_AVAILABLE = True
    except ImportError:
        NUMPY_SCIPY_AVAILABLE = False

    if not NUMPY_SCIPY_AVAILABLE:
        print(f"{Fore.RED}Cannot mix audio tracks: numpy, scipy, or soundfile not available.{Style.RESET_ALL}")
        return None

    print(f"\n{Fore.CYAN}Attempting to mix audio tracks...{Style.RESET_ALL}")
    try:
        # Read both audio files
        audio1, sr1 = sf.read(track1_path)
        audio2, sr2 = sf.read(track2_path)

        # Ensure both files have the same sample rate
        if sr1 != sr2:
            print(f"{Fore.YELLOW}Warning: Sample rates differ ({sr1} vs {sr2}). Resampling for mixing.{Style.RESET_ALL}")
            if sr1 < sr2:
                num = int(audio2.shape[0] * sr1 / sr2)
                audio2 = signal.resample(audio2, num)
            elif sr2 < sr1:
                num = int(audio1.shape[0] * sr2 / sr1)
                audio1 = signal.resample(audio1, num)
                sr1 = sr2

        # Handle stereo vs mono: convert to mono if needed
        if audio1.ndim > 1:
            audio1 = audio1.mean(axis=1)
        if audio2.ndim > 1:
            audio2 = audio2.mean(axis=1)

        # Adjust volumes
        audio1 = audio1 * volume1
        audio2 = audio2 * volume2

        # Determine the length of the longer audio
        max_len = max(len(audio1), len(audio2))
        
        # Pad both arrays to the same length if needed
        if len(audio1) < max_len:
            audio1 = np.pad(audio1, (0, max_len - len(audio1)), 'constant')
        if len(audio2) < max_len:
            audio2 = np.pad(audio2, (0, max_len - len(audio2)), 'constant')

        # Mix the audio by adding the two signals
        mixed_audio = audio1 + audio2

        # Normalize to prevent clipping (optional)
        max_amplitude = np.max(np.abs(mixed_audio))
        if max_amplitude > 1.0:
            mixed_audio = mixed_audio / max_amplitude
            print(f"{Fore.YELLOW}Audio normalized to prevent clipping.{Style.RESET_ALL}")

        # Write the mixed audio to file
        sf.write(output_mixed_path, mixed_audio, sr1)

        print(f"{Fore.GREEN}\N{check mark} Audio tracks mixed successfully and saved to {output_mixed_path}.{Style.RESET_ALL}")
        return output_mixed_path

    except FileNotFoundError:
        print(f"{Fore.RED}Error: One of the audio files for mixing was not found.{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An error occurred during audio mixing: {e}{Style.RESET_ALL}")
        return None
