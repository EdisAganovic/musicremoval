import numpy as np
from scipy import signal
import soundfile as sf
from colorama import Fore, Style

def align_audio_tracks(track1_path, track2_path, output_aligned_track1_path, output_aligned_track2_path):
    """
    Aligns two audio tracks using cross-correlation.
    Pads the beginning of the track that starts earlier.
    Saves the aligned tracks to new paths.

    Returns the paths to the aligned tracks, or None if alignment fails.
    """
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

    print(f"\n{Fore.CYAN}Attempting to align audio tracks using cross-correlation...{Style.RESET_ALL}")
    try:
        audio1, sr1 = sf.read(track1_path)
        audio2, sr2 = sf.read(track2_path)

        if sr1 != sr2:
            print(f"{Fore.YELLOW}Warning: Sample rates differ ({sr1} vs {sr2}). Resampling for alignment.{Style.RESET_ALL}")
            if sr1 < sr2:
                num = int(audio2.shape[0] * sr1 / sr2)
                audio2 = signal.resample(audio2, num)
            elif sr2 < sr1:
                num = int(audio1.shape[0] * sr2 / sr1)
                audio1 = signal.resample(audio1, num)
                sr1 = sr2
        
        if audio1.ndim > 1:
            audio1 = audio1.mean(axis=1)
        if audio2.ndim > 1:
            audio2 = audio2.mean(axis=1)

        len1 = len(audio1)
        len2 = len(audio2)
        max_len = max(len1, len2)

        padded_audio1 = np.pad(audio1, (0, max_len - len1), 'constant')
        padded_audio2 = np.pad(audio2, (0, max_len - len2), 'constant')

        correlation = signal.correlate(padded_audio1, padded_audio2, mode='full')
        delay_samples = np.argmax(correlation) - (max_len - 1)
        delay_ms = (delay_samples / sr1) * 1000

        print(f"{Fore.BLUE}Calculated audio delay: {delay_ms:.2f} ms ({delay_samples} samples){Style.RESET_ALL}")

        aligned_audio1 = audio1
        aligned_audio2 = audio2

        if delay_samples > 0:
            print(f"{Fore.BLUE}Padding Track 2 (Demucs) by {delay_ms:.2f} ms.{Style.RESET_ALL}")
            aligned_audio2 = np.pad(audio2, (delay_samples, 0), 'constant')
            aligned_audio1 = np.pad(audio1, (0, max(0, len(aligned_audio2) - len(audio1))), 'constant')
        elif delay_samples < 0:
            print(f"{Fore.BLUE}Padding Track 1 (Spleeter) by {-delay_ms:.2f} ms.{Style.RESET_ALL}")
            aligned_audio1 = np.pad(audio1, (-delay_samples, 0), 'constant')
            aligned_audio2 = np.pad(audio2, (0, max(0, len(aligned_audio1) - len(audio2))), 'constant')
        else:
            print(f"{Fore.GREEN}Tracks are already aligned. No padding needed.{Style.RESET_ALL}")
            max_orig_len = max(len1, len2)
            aligned_audio1 = np.pad(audio1, (0, max(0, max_orig_len - len1)), 'constant')
            aligned_audio2 = np.pad(audio2, (0, max(0, max_orig_len - len2)), 'constant')

        sf.write(output_aligned_track1_path, aligned_audio1, sr1)
        sf.write(output_aligned_track2_path, aligned_audio2, sr2)

        print(f"{Fore.GREEN}\N{check mark} Audio tracks aligned and saved.{Style.RESET_ALL}")
        return output_aligned_track1_path, output_aligned_track2_path

    except FileNotFoundError:
        print(f"{Fore.RED}Error: One of the audio files for alignment was not found.{Style.RESET_ALL}")
        return None, None
    except Exception as e:
        print(f"{Fore.RED}An error occurred during audio alignment: {e}{Style.RESET_ALL}")
        return None, None
