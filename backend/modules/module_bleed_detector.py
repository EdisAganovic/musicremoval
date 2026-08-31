"""
MODULE: module_bleed_detector.py - AI MUSIC BLEED & HARMONIC ENERGY SCANNER

ROLE: Fast spectral analysis scanner that detects residual background music bleed
      in dialogue and sound effects (SFX) stems using harmonic spectral flux and peak energy.
"""
import os
import numpy as np
import soundfile as sf
from scipy.signal import stft


def detect_music_bleed(audio_path: str, min_confidence: float = 0.5, hop_sec: float = 0.25):
    """
    Scans an audio stem for tonal harmonic energy and sustained musical patterns.

    Args:
        audio_path: Path to the stem WAV/MP3 file.
        min_confidence: Confidence threshold (0.0 to 1.0).
        hop_sec: Time resolution in seconds for detection windows.

    Returns:
        list of dicts: [
            {"start": float, "end": float, "confidence": float, "duration": float, "label": str}
        ]
    """
    if not os.path.exists(audio_path):
        return []

    try:
        data, sr = sf.read(audio_path, dtype='float32')
    except Exception as e:
        print(f"Error reading audio for bleed detection: {e}")
        return []

    if data.ndim > 1:
        data = np.mean(data, axis=1)

    total_duration = len(data) / sr
    if total_duration < 1.0:
        return []

    # Compute STFT for spectral flux & tonal energy
    nperseg = int(sr * 0.05)  # 50ms window
    if nperseg % 2 != 0:
        nperseg += 1
    noverlap = int(nperseg * 0.5)

    f, t, Zxx = stft(data, fs=sr, nperseg=nperseg, noverlap=noverlap)
    magnitude = np.abs(Zxx)  # [freq_bins, time_frames]

    # Musical frequency band focus: 150 Hz to 4000 Hz
    freq_mask = (f >= 150) & (f <= 4000)
    mag_music_band = magnitude[freq_mask, :]

    if mag_music_band.shape[0] == 0 or mag_music_band.shape[1] == 0:
        return []

    # 1. Spectral Flatness: Music has peaks (low flatness/high tonality), white noise/transients have high flatness
    geom_mean = np.exp(np.mean(np.log(mag_music_band + 1e-10), axis=0))
    arith_mean = np.mean(mag_music_band, axis=0) + 1e-10
    spectral_flatness = geom_mean / arith_mean
    tonality = 1.0 - np.clip(spectral_flatness, 0.0, 1.0)

    # 2. RMS Energy envelope
    rms = np.sqrt(np.mean(mag_music_band ** 2, axis=0))
    max_rms = np.max(rms) if np.max(rms) > 0 else 1.0
    norm_rms = np.clip(rms / max_rms, 0.0, 1.0)

    # 3. Harmonic Bleed Score (High tonality + significant energy)
    bleed_score = tonality * np.sqrt(norm_rms)
    
    # Smooth score with a moving average over ~0.5s
    smooth_win = int(0.5 / (t[1] - t[0])) if len(t) > 1 else 5
    smooth_win = max(smooth_win, 1)
    kernel = np.ones(smooth_win) / smooth_win
    smoothed_bleed = np.convolve(bleed_score, kernel, mode='same')

    # Normalize to 0.0 - 1.0 range
    q95 = np.percentile(smoothed_bleed, 95) if len(smoothed_bleed) > 0 else 1.0
    if q95 > 0:
        normalized_scores = np.clip(smoothed_bleed / q95, 0.0, 1.0)
    else:
        normalized_scores = smoothed_bleed

    # Detect contiguous regions exceeding threshold
    threshold = max(min_confidence, 0.45)
    is_bleed = normalized_scores > threshold

    regions = []
    in_region = False
    region_start = 0.0
    conf_values = []

    time_step = t[1] - t[0] if len(t) > 1 else hop_sec

    for idx, flag in enumerate(is_bleed):
        cur_t = float(t[idx]) if idx < len(t) else float(idx * time_step)
        if flag and not in_region:
            in_region = True
            region_start = max(0.0, cur_t - 0.2)  # slight pre-roll
            conf_values = [float(normalized_scores[idx])]
        elif flag and in_region:
            conf_values.append(float(normalized_scores[idx]))
        elif not flag and in_region:
            in_region = False
            region_end = min(total_duration, cur_t + 0.2)  # slight post-roll
            dur = region_end - region_start
            if dur >= 0.8:  # ignore sub-second noise spikes
                avg_conf = float(np.mean(conf_values))
                regions.append({
                    "start": round(region_start, 2),
                    "end": round(region_end, 2),
                    "duration": round(dur, 2),
                    "confidence": round(avg_conf, 2),
                    "label": f"Residual Music ({round(avg_conf * 100)}%)"
                })

    if in_region:
        region_end = float(total_duration)
        dur = region_end - region_start
        if dur >= 0.8:
            avg_conf = float(np.mean(conf_values)) if conf_values else 0.7
            regions.append({
                "start": round(region_start, 2),
                "end": round(region_end, 2),
                "duration": round(dur, 2),
                "confidence": round(avg_conf, 2),
                "label": f"Residual Music ({round(avg_conf * 100)}%)"
            })

    # Merge regions that are closer than 1.0s apart
    merged = []
    for r in regions:
        if not merged:
            merged.append(r)
        else:
            prev = merged[-1]
            if r["start"] - prev["end"] < 1.0:
                prev["end"] = r["end"]
                prev["duration"] = round(prev["end"] - prev["start"], 2)
                prev["confidence"] = round(max(prev["confidence"], r["confidence"]), 2)
            else:
                merged.append(r)

    return merged
