"""
ROUTE: audio_project.py - MULTI-TRACK AUDIO PROJECT & DUBBING STUDIO

ROLE: Complete API backend for Audio Projects:
      - Project workspace management & state persistence
      - Multi-Model separation pass stacking (TIGER, Roformer, Demucs, Spleeter)
      - External voiceover/dubbing track import
      - AI Music Bleed Heatmap Scanner
      - NumPy Hann-fade mixer with Soft-Knee True-Peak Limiting
      - Direct video remuxing
      - Preset templates
"""
import os
import sys
import json
import time
import uuid
import shutil
import asyncio
import numpy as np
import soundfile as sf
import urllib.parse
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from colorama import Fore, Style
from core.constants import (
    DEFAULT_ROFORMER_MODEL,
    DEFAULT_TIGER_TARGET,
    DEFAULT_TIGER_OVERLAP,
)

# Project directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modules")))

PROJECTS_DIR = os.path.abspath("projects")
PRESETS_FILE = os.path.abspath("data/project_presets.json")
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

router = APIRouter(prefix="/api/project", tags=["audio_project"])


# -------------------------------------------------------------
# PYDANTIC SCHEMAS
# -------------------------------------------------------------

class RegionCut(BaseModel):
    id: str
    start: float
    end: float
    fade_in_ms: int = 100
    fade_out_ms: int = 100
    label: Optional[str] = "Silenced Region"


class TrackState(BaseModel):
    id: str
    name: str
    model: str
    stem_type: str
    file_path: str
    audio_url: str
    color: str
    volume: float = 1.0
    pan: float = 0.0
    muted: bool = False
    solo: bool = False
    cuts: List[RegionCut] = []
    bleed_regions: List[Dict[str, Any]] = []
    peaks: Optional[Dict[str, Any]] = None


class ProjectSaveRequest(BaseModel):
    project_name: Optional[str] = None
    tracks: List[TrackState]


class RunPassRequest(BaseModel):
    pass_name: str
    model: str  # "tiger", "roformer", "demucs", "spleeter"
    roformer_model: Optional[str] = DEFAULT_ROFORMER_MODEL
    tiger_target: Optional[str] = DEFAULT_TIGER_TARGET
    tiger_overlap: Optional[int] = DEFAULT_TIGER_OVERLAP
    demucs_stems: Optional[int] = 4  # 2 or 4
    spleeter_stems: Optional[int] = 2  # 2, 4, or 5


class ScanBleedRequest(BaseModel):
    track_id: str
    min_confidence: Optional[float] = 0.5


class SavePresetRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    settings: Dict[str, Any]


# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------

def get_project_dir(project_id: str) -> str:
    return os.path.join(PROJECTS_DIR, project_id)


def get_project_json_path(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "project.json")


def load_project_json(project_id: str) -> dict:
    p_path = get_project_json_path(project_id)
    if not os.path.exists(p_path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(p_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project_json(project_id: str, data: dict):
    p_path = get_project_json_path(project_id)
    with open(p_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def compute_audio_peaks(file_path: str, num_points: int = 1200) -> dict:
    """Computes downsampled min/max peaks for instant 0ms waveform rendering in the frontend."""
    if not file_path or not os.path.exists(file_path):
        return {"min": [], "max": []}
    try:
        data, _sr = sf.read(file_path, always_2d=True)
        mono = np.mean(data, axis=1)
        total_samples = len(mono)
        if total_samples == 0:
            return {"min": [], "max": []}

        block_size = max(1, total_samples // num_points)
        usable = (total_samples // block_size) * block_size
        if usable == 0:
            return {
                "min": [round(float(np.min(mono)), 3)],
                "max": [round(float(np.max(mono)), 3)]
            }

        reshaped = mono[:usable].reshape(-1, block_size)
        mins = np.min(reshaped, axis=1)
        maxs = np.max(reshaped, axis=1)

        return {
            "min": [round(float(v), 3) for v in mins[:num_points].tolist()],
            "max": [round(float(v), 3) for v in maxs[:num_points].tolist()]
        }
    except Exception as e:
        print(f"Error computing peaks for {file_path}: {e}")
        return {"min": [], "max": []}


def soft_knee_limiter(audio_data: np.ndarray, threshold_db: float = -0.5) -> np.ndarray:
    """Applies soft-knee True-Peak limiting to prevent digital distortion."""
    peak = np.max(np.abs(audio_data))
    limit_val = 10.0 ** (threshold_db / 20.0)  # ~0.944 for -0.5dB
    if peak > limit_val:
        scale = limit_val / peak
        return audio_data * scale
    return audio_data


# -------------------------------------------------------------
# PROJECT CRUD & MANAGEMENT
# -------------------------------------------------------------

@router.get("/stream-video")
@router.get("/stream-audio")
async def stream_project_media(file: Optional[str] = None, path: Optional[str] = None):
    """Streams reference video/audio with HTTP byte-range support."""
    target = file or path
    if not target:
        raise HTTPException(status_code=400, detail="Missing file parameter")

    raw_path = target.strip().strip('"').strip("'")
    if raw_path.startswith("file:///"):
        raw_path = raw_path[8:]
    elif raw_path.startswith("file://"):
        raw_path = raw_path[7:]

    candidates = [raw_path]
    try:
        unquoted = urllib.parse.unquote(raw_path)
        if unquoted != raw_path:
            candidates.append(unquoted)
    except Exception:
        pass

    clean_path = None
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    for cand in candidates:
        cand_abs = os.path.abspath(os.path.normpath(cand))
        if os.path.isfile(cand_abs):
            clean_path = cand_abs
            break
        rel_cand = os.path.abspath(os.path.join(project_root, cand))
        if os.path.isfile(rel_cand):
            clean_path = rel_cand
            break

    if not clean_path:
        raise HTTPException(status_code=404, detail=f"Media file not found: {raw_path}")

    # SECURITY: only serve files from allowed project directories
    from core.constants import DOWNLOAD_DIR, NOMUSIC_DIR
    _allowed = [
        NOMUSIC_DIR,
        DOWNLOAD_DIR,
        os.path.abspath("uploads"),
        os.path.abspath("projects"),
        os.path.abspath("."),
    ]
    clean_lower = clean_path.lower()
    if not any(clean_lower.startswith(r.lower()) or clean_lower == r.lower() for r in _allowed):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")

    ext = os.path.splitext(clean_path)[1].lower()
    media_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.aac': 'audio/aac',
        '.flac': 'audio/flac',
        '.ogg': 'audio/ogg'
    }
    media_type = media_types.get(ext, 'video/mp4')
    filename = os.path.basename(clean_path)
    encoded_filename = urllib.parse.quote(filename)

    return FileResponse(
        path=clean_path,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length, Content-Type",
        }
    )


@router.get("")
@router.get("/")
@router.get("s")
async def list_projects():
    """List all audio projects."""
    projects = []
    for pid in os.listdir(PROJECTS_DIR):
        p_dir = os.path.join(PROJECTS_DIR, pid)
        if os.path.isdir(p_dir):
            p_json = os.path.join(p_dir, "project.json")
            if os.path.exists(p_json):
                try:
                    with open(p_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        projects.append({
                            "id": data.get("id", pid),
                            "name": data.get("name", "Untitled Project"),
                            "created_at": data.get("created_at", 0),
                            "updated_at": data.get("updated_at", 0),
                            "source_name": data.get("source_name", ""),
                            "duration": data.get("duration", 0),
                            "track_count": len(data.get("tracks", [])),
                            "has_video": bool(data.get("video_file"))
                        })
                except Exception:
                    pass
    projects.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return {"projects": projects}


@router.delete("/{project_id}")
@router.post("/{project_id}/delete")
async def delete_project(project_id: str):
    """Deletes an entire audio project workspace."""
    p_dir = os.path.join(PROJECTS_DIR, project_id)
    if os.path.exists(p_dir):
        try:
            shutil.rmtree(p_dir)
            return {"success": True, "message": f"Project {project_id} deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete project directory: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/create")
async def create_project(
    project_name: str = Form("New Audio Project"),
    file: Optional[UploadFile] = File(None),
    library_path: Optional[str] = Form(None),
    duration: Optional[float] = Form(None)
):
    """Creates a new Audio Studio Project workspace."""
    from modules.module_ffmpeg import FFMPEG_EXE, get_file_metadata, tracked_run

    project_id = str(uuid.uuid4())[:12]
    p_dir = get_project_dir(project_id)
    stems_dir = os.path.join(p_dir, "stems")
    os.makedirs(stems_dir, exist_ok=True)

    source_path = None
    original_filename = ""
    is_video = False

    if file and hasattr(file, 'filename') and file.filename:
        original_filename = file.filename
        ext = os.path.splitext(file.filename)[1]
        raw_source = os.path.join(p_dir, f"source_raw{ext}")
        with open(raw_source, "wb") as buffer:
            buffer.write(await file.read())
        source_path = raw_source
    elif library_path and os.path.exists(library_path):
        original_filename = os.path.basename(library_path)
        ext = os.path.splitext(library_path)[1]
        raw_source = os.path.join(p_dir, f"source_raw{ext}")
        shutil.copy2(library_path, raw_source)
        source_path = raw_source
    else:
        raise HTTPException(status_code=400, detail="No valid file or library path provided")

    metadata = get_file_metadata(source_path)
    is_video = metadata.get("is_video", False)
    total_duration = metadata.get("duration", 0)
    if total_duration == "N/A" or not total_duration:
        total_duration = 30.0
    else:
        try:
            total_duration = float(total_duration)
        except Exception:
            total_duration = 30.0

    if duration and float(duration) > 0:
        total_duration = min(total_duration, float(duration))

    # Extract clean source 44.1kHz stereo WAV
    source_wav = os.path.join(p_dir, "source.wav")
    extract_cmd = [FFMPEG_EXE, "-y", "-i", source_path]
    if duration and float(duration) > 0:
        extract_cmd.extend(["-t", str(duration)])
    extract_cmd.extend(["-vn", "-ac", "2", "-ar", "44100", source_wav])
    tracked_run(extract_cmd, check=True)

    video_rel_path = None
    if is_video:
        video_rel_path = f"/projects/{project_id}/{os.path.basename(source_path)}"

    # Initial original source track
    initial_tracks = [
        {
            "id": f"tr_source_{uuid.uuid4().hex[:6]}",
            "name": f"📼 [Original] {original_filename or 'Source Audio'}",
            "model": "source",
            "stem_type": "original",
            "file_path": source_wav,
            "audio_url": f"/projects/{project_id}/source.wav",
            "color": "#38bdf8",
            "volume": 1.0,
            "muted": False,
            "solo": False,
            "cuts": [],
            "bleed_regions": [],
            "peaks": compute_audio_peaks(source_wav)
        }
    ]

    # Initial project state
    project_data = {
        "id": project_id,
        "name": project_name,
        "source_name": original_filename,
        "source_raw": source_path,
        "source_wav": source_wav,
        "video_file": source_path if is_video else None,
        "video_url": video_rel_path,
        "is_video": is_video,
        "duration": total_duration,
        "created_at": time.time(),
        "updated_at": time.time(),
        "passes": [],
        "tracks": initial_tracks
    }

    save_project_json(project_id, project_data)
    print(f"{Fore.GREEN}[Audio Studio] Created Project '{project_name}' (ID: {project_id}) with initial Source track & precomputed peaks.{Style.RESET_ALL}")

    return {"project": project_data}


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Retrieve full project details with precomputed waveform peaks."""
    data = load_project_json(project_id)
    changed = False

    # Ensure source track is always present as reference
    has_orig = any(t.get("stem_type") == "original" for t in data.get("tracks", []))
    if not has_orig and data.get("source_wav") and os.path.exists(data.get("source_wav")):
        orig_track = {
            "id": f"tr_source_{project_id[:6]}",
            "name": f"📼 [Original] {data.get('source_name') or 'Source Audio'}",
            "model": "source",
            "stem_type": "original",
            "file_path": data.get("source_wav"),
            "audio_url": f"/projects/{project_id}/source.wav",
            "color": "#38bdf8",
            "volume": 1.0,
            "muted": False,
            "solo": False,
            "cuts": [],
            "bleed_regions": [],
            "peaks": compute_audio_peaks(data.get("source_wav"))
        }
        data.setdefault("tracks", []).insert(0, orig_track)
        changed = True

    # Precompute / backfill missing peaks for all tracks
    for t in data.get("tracks", []):
        if not t.get("peaks") or not t["peaks"].get("min") or len(t["peaks"]["min"]) == 0:
            fp = t.get("file_path")
            if fp and os.path.exists(fp):
                t["peaks"] = compute_audio_peaks(fp)
                changed = True

    if changed:
        save_project_json(project_id, data)

    return {"project": data}


@router.post("/{project_id}/expand-full-duration")
async def expand_full_duration(project_id: str):
    """Re-extracts source audio to the 100% full duration of the raw media file."""
    from modules.module_ffmpeg import FFMPEG_EXE, get_audio_duration, tracked_run

    p_dir = get_project_dir(project_id)
    data = load_project_json(project_id)
    source_raw = data.get("source_raw")

    if not source_raw or not os.path.exists(source_raw):
        raise HTTPException(status_code=400, detail="Raw media file not found on disk")

    full_dur = get_audio_duration(source_raw)
    if not full_dur or full_dur <= 0:
        raise HTTPException(status_code=400, detail="Could not determine media duration")

    source_wav = os.path.join(p_dir, "source.wav")
    extract_cmd = [FFMPEG_EXE, "-y", "-i", source_raw, "-vn", "-ac", "2", "-ar", "44100", source_wav]
    tracked_run(extract_cmd, check=True)

    data["duration"] = float(full_dur)
    save_project_json(project_id, data)
    print(f"{Fore.GREEN}[Audio Studio] Expanded Project '{data.get('name')}' to full duration: {full_dur:.2f}s{Style.RESET_ALL}")
    return {"project": data, "duration": full_dur}


@router.delete("/{project_id}/track/{track_id}")
async def delete_project_track(project_id: str, track_id: str):
    """Deletes a track from the project and removes its stem file from disk."""
    data = load_project_json(project_id)
    tracks = data.get("tracks", [])
    target = next((t for t in tracks if t["id"] == track_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Track not found in project")

    # If it's a generated or imported stem (not the source_wav), delete file from disk
    file_path = target.get("file_path")
    source_wav = data.get("source_wav")
    if file_path and os.path.exists(file_path) and os.path.abspath(file_path) != os.path.abspath(source_wav or ""):
        try:
            os.remove(file_path)
            print(f"[Audio Studio] Removed stem file from disk: {file_path}")
        except Exception as e:
            print(f"Warning: Could not remove stem file {file_path}: {e}")

    data["tracks"] = [t for t in tracks if t["id"] != track_id]
    data["updated_at"] = time.time()
    save_project_json(project_id, data)
    return {"status": "deleted", "track_id": track_id, "project": data}


@router.post("/{project_id}/track/{track_id}/normalize")
async def normalize_track(project_id: str, track_id: str, target_peak_db: float = -0.5):
    """Applies True-Peak normalization to a track audio file."""
    data = load_project_json(project_id)
    track = next((t for t in data.get("tracks", []) if t["id"] == track_id), None)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = track.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Track audio file not found on disk")

    def _do_normalize():
        audio_np, sr = sf.read(file_path, dtype='float32')
        current_peak = np.max(np.abs(audio_np))
        if current_peak < 1e-6:
            return 1.0, 0.0
        target_linear = 10.0 ** (target_peak_db / 20.0)
        gain_factor = target_linear / current_peak
        normalized_audio = audio_np * gain_factor
        sf.write(file_path, normalized_audio, sr)
        return float(gain_factor), float(current_peak)

    gain_factor, orig_peak = await asyncio.to_thread(_do_normalize)
    data["updated_at"] = time.time()
    save_project_json(project_id, data)
    print(f"[Audio Studio] Normalized track '{track.get('name')}' (Peak: {orig_peak:.3f} -> Gain: {gain_factor:.2f}x)")
    return {"status": "normalized", "gain_factor": gain_factor, "project": data}


# -------------------------------------------------------------
# MULTI-MODEL SEPARATION PASS STACKING
# -------------------------------------------------------------

def _execute_separation_pass_sync(project_id: str, payload: RunPassRequest) -> tuple:
    data = load_project_json(project_id)
    p_dir = get_project_dir(project_id)
    stems_dir = os.path.join(p_dir, "stems")
    source_wav = data["source_wav"]

    if not os.path.exists(source_wav):
        raise HTTPException(status_code=404, detail="Source audio WAV not found in project")

    pass_id = str(uuid.uuid4())[:6]
    pass_name = payload.pass_name.strip() or f"Pass {len(data.get('passes', [])) + 1}"
    model = payload.model.lower()
    new_tracks = []

    print(f"\n{Fore.CYAN}=== Running Separation Pass: '{pass_name}' ({model.upper()}) ==={Style.RESET_ALL}")

    if model == "tiger":
        # PyTorch CUDA TIGER-DnR 3-Stem Extraction
        import look2hear.models
        from modules.module_tiger import get_tiger_model
        tiger_model, device = get_tiger_model()

        audio_np, orig_sr = sf.read(source_wav, dtype='float32')
        TARGET_SR = 44100
        if audio_np.ndim > 1:
            mono_audio = np.mean(audio_np, axis=1)
        else:
            mono_audio = audio_np

        if orig_sr != TARGET_SR:
            import resampy
            mono_audio = resampy.resample(mono_audio, orig_sr, TARGET_SR)

        wav_tensor = torch_tensor = __import__("torch").from_numpy(mono_audio).unsqueeze(0).unsqueeze(0).to(device)
        hop_sec = 3.0 if (payload.tiger_overlap or 50) >= 75 else 6.0

        with __import__("torch").inference_mode():
            with __import__("torch").autocast('cuda', dtype=__import__("torch").float16, enabled=(device.type == 'cuda')):
                d_out, e_out, m_out = tiger_model(wav_tensor, target_length=12.0, hop_length=hop_sec, batch_size=4)

        d_wav = d_out.squeeze().to(__import__("torch").float32).cpu().numpy()
        e_wav = e_out.squeeze().to(__import__("torch").float32).cpu().numpy()
        m_wav = m_out.squeeze().to(__import__("torch").float32).cpu().numpy()

        stems_info = [
            ("dialogue", "🗣️ Dialogue", d_wav, "#38bdf8"),               # Sky blue
            ("sfx", "💥 Sound Effects (Foley)", e_wav, "#f59e0b"),        # Amber
            ("music", "🎼 Background Score", m_wav, "#ec4899")            # Pink
        ]

        for stem_type, track_label, stem_audio, color in stems_info:
            stem_filename = f"{pass_id}_{stem_type}.wav"
            stem_path = os.path.join(stems_dir, stem_filename)
            sf.write(stem_path, stem_audio, TARGET_SR)
            track_id = f"tr_{uuid.uuid4().hex[:8]}"
            new_tracks.append({
                "id": track_id,
                "name": track_label,
                "model": "tiger",
                "stem_type": stem_type,
                "file_path": stem_path,
                "audio_url": f"/projects/{project_id}/stems/{stem_filename}",
                "color": color,
                "volume": 1.0,
                "muted": (stem_type == "music"), # Mute music by default for clean mix
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })

    elif model == "roformer":
        # Mel-Band Roformer / MSST Separation
        from modules.module_roformer import separate_with_roformer
        roformer_ckpt = payload.roformer_model or "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"
        temp_out = os.path.join(p_dir, f"_temp_roformer_{pass_id}")
        vocal_path, music_path, _ = separate_with_roformer(
            source_wav, temp_out, f"roformer_{pass_id}",
            roformer_model=roformer_ckpt,
            want_instrumental=True
        )

        if vocal_path and os.path.exists(vocal_path):
            target_file = os.path.join(stems_dir, f"{pass_id}_roformer_vocals_sfx.wav")
            shutil.move(vocal_path, target_file)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🎬 Clean Voice & Foley",
                "model": "roformer",
                "stem_type": "dialogue_sfx",
                "file_path": target_file,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_file)}",
                "color": "#06b6d4", # Cyan
                "volume": 1.0,
                "muted": False,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })

        if music_path and os.path.exists(music_path):
            target_music = os.path.join(stems_dir, f"{pass_id}_roformer_music.wav")
            shutil.move(music_path, target_music)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🎼 Background Music",
                "model": "roformer",
                "stem_type": "music",
                "file_path": target_music,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_music)}",
                "color": "#a855f7", # Purple
                "volume": 1.0,
                "muted": True,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })
        shutil.rmtree(temp_out, ignore_errors=True)

    elif model == "demucs":
        # Demucs 4-Stem / 2-Stem
        from modules.module_demucs import separate_with_demucs
        temp_out = os.path.join(p_dir, f"_temp_demucs_{pass_id}")
        demucs_stems = payload.demucs_stems or 4
        stem_out, inst_out, _ = separate_with_demucs(source_wav, temp_out, f"demucs_{pass_id}", want_instrumental=True)

        if stem_out and os.path.exists(stem_out):
            target_file = os.path.join(stems_dir, f"{pass_id}_demucs_vocals.wav")
            shutil.move(stem_out, target_file)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🎙️ Demucs Vocals",
                "model": "demucs",
                "stem_type": "vocals",
                "file_path": target_file,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_file)}",
                "color": "#8b5cf6",
                "volume": 1.0,
                "muted": False,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })
        if inst_out and os.path.exists(inst_out):
            target_inst = os.path.join(stems_dir, f"{pass_id}_demucs_no_vocals.wav")
            shutil.move(inst_out, target_inst)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🥁 Demucs Accompaniment",
                "model": "demucs",
                "stem_type": "accompaniment",
                "file_path": target_inst,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_inst)}",
                "color": "#6366f1",
                "volume": 1.0,
                "muted": True,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })
        shutil.rmtree(temp_out, ignore_errors=True)

    else:
        # Spleeter 2-Stem / 4-Stem
        from modules.module_spleeter import separate_with_spleeter
        temp_out = os.path.join(p_dir, f"_temp_spleeter_{pass_id}")
        sp_vocals, sp_inst, _ = separate_with_spleeter(source_wav, temp_out, f"spleeter_{pass_id}", want_instrumental=True)
        if sp_vocals and os.path.exists(sp_vocals):
            target_file = os.path.join(stems_dir, f"{pass_id}_spleeter_vocals.wav")
            shutil.move(sp_vocals, target_file)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🗣️ Spleeter Vocals",
                "model": "spleeter",
                "stem_type": "vocals",
                "file_path": target_file,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_file)}",
                "color": "#10b981", # Emerald
                "volume": 1.0,
                "muted": False,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })
        if sp_inst and os.path.exists(sp_inst):
            target_inst = os.path.join(stems_dir, f"{pass_id}_spleeter_inst.wav")
            shutil.move(sp_inst, target_inst)
            new_tracks.append({
                "id": f"tr_{uuid.uuid4().hex[:8]}",
                "name": "🎹 Spleeter Accompaniment",
                "model": "spleeter",
                "stem_type": "music",
                "file_path": target_inst,
                "audio_url": f"/projects/{project_id}/stems/{os.path.basename(target_inst)}",
                "color": "#14b8a6",
                "volume": 1.0,
                "muted": True,
                "solo": False,
                "cuts": [],
                "bleed_regions": []
            })
        shutil.rmtree(temp_out, ignore_errors=True)

    # Append pass metadata and new tracks to project with precomputed waveform peaks
    for nt in new_tracks:
        if not nt.get("peaks") or not nt["peaks"].get("min"):
            fp = nt.get("file_path")
            if fp and os.path.exists(fp):
                nt["peaks"] = compute_audio_peaks(fp)

    data.setdefault("passes", []).append({
        "id": pass_id,
        "name": pass_name,
        "model": model,
        "timestamp": time.time(),
        "track_ids": [t["id"] for t in new_tracks]
    })
    data.setdefault("tracks", []).extend(new_tracks)
    data["updated_at"] = time.time()
    save_project_json(project_id, data)

    print(f"{Fore.GREEN}[Audio Studio] Pass '{pass_name}' finished! Added {len(new_tracks)} tracks with waveform peaks.{Style.RESET_ALL}")
    return data, new_tracks


@router.post("/{project_id}/run-pass")
async def run_separation_pass(project_id: str, payload: RunPassRequest):
    """
    Executes a separation model pass on a worker thread and stacks the extracted stems as project tracks.
    """
    updated_data, new_tracks = await asyncio.to_thread(_execute_separation_pass_sync, project_id, payload)
    return {"project": updated_data, "new_tracks": new_tracks}


# -------------------------------------------------------------
# EXTERNAL DUBBING & VOICEOVER IMPORT
# -------------------------------------------------------------

@router.post("/{project_id}/import-track")
async def import_external_track(
    project_id: str,
    file: UploadFile = File(...),
    track_name: str = Form("🎙️ External Dub / Voiceover")
):
    """Import an external audio file (e.g. translated dubbing) as a synchronized stem track."""
    data = load_project_json(project_id)
    p_dir = get_project_dir(project_id)
    stems_dir = os.path.join(p_dir, "stems")

    track_id = f"tr_{uuid.uuid4().hex[:8]}"
    ext = os.path.splitext(file.filename)[1] or ".wav"
    dest_filename = f"import_{track_id}{ext}"
    dest_path = os.path.join(stems_dir, dest_filename)

    with open(dest_path, "wb") as buffer:
        buffer.write(await file.read())

    # Convert to standard 44.1kHz WAV if not WAV
    final_wav_path = dest_path
    if not dest_path.lower().endswith(".wav"):
        final_wav_path = os.path.join(stems_dir, f"import_{track_id}.wav")
        from modules.module_ffmpeg import FFMPEG_EXE, tracked_run
        await asyncio.to_thread(tracked_run, [FFMPEG_EXE, "-y", "-i", dest_path, "-ar", "44100", "-ac", "2", final_wav_path], check=True)

    peaks = await asyncio.to_thread(compute_audio_peaks, final_wav_path)

    new_track = {
        "id": track_id,
        "name": track_name,
        "model": "external",
        "stem_type": "voiceover",
        "file_path": final_wav_path,
        "audio_url": f"/projects/{project_id}/stems/{os.path.basename(final_wav_path)}",
        "color": "#10b981", # Emerald
        "volume": 1.0,
        "muted": False,
        "solo": False,
        "cuts": [],
        "bleed_regions": [],
        "peaks": peaks
    }

    data.setdefault("tracks", []).append(new_track)
    data["updated_at"] = time.time()
    save_project_json(project_id, data)

    return {"project": data, "track": new_track}


# -------------------------------------------------------------
# AI MUSIC BLEED SCANNER
# -------------------------------------------------------------

@router.post("/{project_id}/scan-bleed")
async def scan_track_bleed(project_id: str, payload: ScanBleedRequest):
    """Scans a stem track for residual background music bleed."""
    from modules.module_bleed_detector import detect_music_bleed
    data = load_project_json(project_id)

    track = next((t for t in data.get("tracks", []) if t["id"] == payload.track_id), None)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    audio_path = track["file_path"]
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Track audio file missing")

    regions = await asyncio.to_thread(detect_music_bleed, audio_path, min_confidence=payload.min_confidence or 0.5)
    track["bleed_regions"] = regions
    save_project_json(project_id, data)

    return {"track_id": payload.track_id, "bleed_regions": regions}


# -------------------------------------------------------------
# SAVE PROJECT STATE (VOLUMES, MUTES, CUTS)
# -------------------------------------------------------------

@router.post("/{project_id}/save-state")
async def save_project_state(project_id: str, payload: ProjectSaveRequest):
    """Persists track volumes, mute/solo states, and cut regions."""
    data = load_project_json(project_id)
    if payload.project_name:
        data["name"] = payload.project_name

    # Update tracks list
    updated_tracks_dict = {t.id: t.dict() for t in payload.tracks}
    for tr in data.get("tracks", []):
        if tr["id"] in updated_tracks_dict:
            tr.update(updated_tracks_dict[tr["id"]])

    data["updated_at"] = time.time()
    save_project_json(project_id, data)
    return {"status": "saved", "project": data}


# -------------------------------------------------------------
# NUMPY HANN-FADE MIXER & TRUE-PEAK LIMITER
# -------------------------------------------------------------

def render_project_mixdown(project_id: str) -> str:
    """
    Renders active stems into a single master WAV with smooth Hann-window cosine crossfades
    on cut/silenced regions and soft-knee True-Peak limiting.
    """
    data = load_project_json(project_id)
    p_dir = get_project_dir(project_id)
    tracks = data.get("tracks", [])

    if not tracks:
        raise HTTPException(status_code=400, detail="No tracks in project to mix")

    # Determine solo state
    has_solo = any(t.get("solo", False) for t in tracks)
    active_tracks = []
    for t in tracks:
        if has_solo:
            if t.get("solo", False):
                active_tracks.append(t)
        else:
            if not t.get("muted", False):
                active_tracks.append(t)

    if not active_tracks:
        raise HTTPException(status_code=400, detail="All tracks are muted")

    # Target sample rate
    TARGET_SR = 44100
    max_len = 0
    loaded_audio = []

    for t in active_tracks:
        path = t["file_path"]
        if not os.path.exists(path):
            continue
        audio_np, sr = sf.read(path, dtype='float32')
        if sr != TARGET_SR:
            import resampy
            audio_np = resampy.resample(audio_np, sr, TARGET_SR)

        if audio_np.ndim == 1:
            audio_np = np.stack([audio_np, audio_np], axis=1)  # Stereo

        # Apply track volume gain
        gain = float(t.get("volume", 1.0))
        audio_np = audio_np * gain

        # Apply track pan (constant-power panning)
        pan = float(t.get("pan", 0.0))
        if pan != 0.0 and audio_np.shape[1] >= 2:
            angle = ((pan + 1.0) / 2.0) * (np.pi / 2.0)
            left_gain = np.cos(angle)
            right_gain = np.sin(angle)
            audio_np[:, 0] *= left_gain
            audio_np[:, 1] *= right_gain

        # Apply region cuts with Hann cosine fade-in / fade-out envelopes
        cuts = t.get("cuts", [])
        for c in cuts:
            c_start = float(c["start"])
            c_end = float(c["end"])
            fade_in_ms = int(c.get("fade_in_ms", 100))
            fade_out_ms = int(c.get("fade_out_ms", 100))

            s_idx = max(0, int(c_start * TARGET_SR))
            e_idx = min(len(audio_np), int(c_end * TARGET_SR))

            if s_idx >= e_idx:
                continue

            cut_samples = e_idx - s_idx
            fade_out_samples = min(int((fade_out_ms / 1000.0) * TARGET_SR), int(cut_samples * 0.48))
            fade_in_samples = min(int((fade_in_ms / 1000.0) * TARGET_SR), int(cut_samples * 0.48))

            # 1. Smooth Fade-Out from s_idx to s_idx + fade_out_samples (1.0 -> 0.0)
            if fade_out_samples > 0:
                ramp_out = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples, endpoint=False)))
                for ch in range(audio_np.shape[1]):
                    audio_np[s_idx:s_idx + fade_out_samples, ch] *= ramp_out

            # 2. Pure silence in middle body from s_idx + fade_out_samples to e_idx - fade_in_samples
            silence_end = e_idx - fade_in_samples if fade_in_samples > 0 else e_idx
            if s_idx + fade_out_samples < silence_end:
                audio_np[s_idx + fade_out_samples:silence_end, :] = 0.0

            # 3. Smooth Fade-In from e_idx - fade_in_samples to e_idx (0.0 -> 1.0)
            if fade_in_samples > 0:
                ramp_in = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples, endpoint=False)))
                for ch in range(audio_np.shape[1]):
                    audio_np[e_idx - fade_in_samples:e_idx, ch] *= ramp_in

        loaded_audio.append(audio_np)
        max_len = max(max_len, len(audio_np))

    if not loaded_audio:
        raise HTTPException(status_code=400, detail="Failed to load any track audio")

    # Sum tracks together
    master_mix = np.zeros((max_len, 2), dtype=np.float32)
    for audio_np in loaded_audio:
        master_mix[:len(audio_np), :] += audio_np

    # Apply True-Peak soft-knee limiter
    master_mix = soft_knee_limiter(master_mix, threshold_db=-0.5)

    # Save output master mixdown WAV
    mixdown_wav = os.path.join(p_dir, "master_mixdown.wav")
    sf.write(mixdown_wav, master_mix, TARGET_SR)

    # Save AAC version with FDK-AAC
    from modules.module_ffmpeg import FFMPEG_EXE, tracked_run
    mixdown_aac = os.path.join(p_dir, "master_mixdown.aac")
    try:
        tracked_run([
            FFMPEG_EXE, "-y", "-i", mixdown_wav,
            "-c:a", "libfdk_aac", "-b:a", "256k",
            mixdown_aac
        ], check=True)
    except Exception:
        tracked_run([
            FFMPEG_EXE, "-y", "-i", mixdown_wav,
            "-c:a", "aac", "-b:a", "256k",
            mixdown_aac
        ], check=False)

    return mixdown_wav


@router.post("/{project_id}/render-mix")
async def render_mix(project_id: str):
    """Renders the master audio mixdown from all active tracks."""
    mix_wav = await asyncio.to_thread(render_project_mixdown, project_id)
    return {
        "status": "ready",
        "mixdown_wav": f"/projects/{project_id}/master_mixdown.wav",
        "mixdown_aac": f"/projects/{project_id}/master_mixdown.aac",
        "filename": "master_mixdown.wav"
    }


# -------------------------------------------------------------
# VIDEO REMUXING
# -------------------------------------------------------------

def _mux_video_sync(project_id: str) -> dict:
    data = load_project_json(project_id)
    p_dir = get_project_dir(project_id)
    video_source = data.get("video_file")

    if not video_source or not os.path.exists(video_source):
        raise HTTPException(status_code=400, detail="Project does not contain a source video file")

    mix_wav = render_project_mixdown(project_id)

    # Output filename in nomusic/
    from core.constants import NOMUSIC_DIR
    os.makedirs(NOMUSIC_DIR, exist_ok=True)
    base_name = os.path.splitext(data.get("source_name", "output"))[0]
    out_video = os.path.abspath(os.path.join(NOMUSIC_DIR, f"remuxed_{base_name}.mp4"))

    from modules.module_ffmpeg import FFMPEG_EXE, tracked_run
    # Remux video stream directly with FDK-AAC audio
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", video_source,
        "-i", mix_wav,
        "-c:v", "copy",
        "-c:a", "libfdk_aac",
        "-b:a", "256k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        out_video
    ]
    try:
        tracked_run(cmd, check=True)
    except Exception:
        cmd[8] = "aac"
        tracked_run(cmd, check=True)

    # Also copy to project directory for browser preview
    proj_remux_video = os.path.join(p_dir, f"remuxed_{base_name}.mp4")
    shutil.copy2(out_video, proj_remux_video)

    return {
        "status": "completed",
        "output_video": out_video,
        "video_url": f"/projects/{project_id}/{os.path.basename(proj_remux_video)}",
        "filename": os.path.basename(out_video)
    }


@router.post("/{project_id}/mux-video")
async def mux_video(project_id: str):
    """Remuxes the master mixdown audio back with the original video without re-encoding."""
    res = await asyncio.to_thread(_mux_video_sync, project_id)
    return res


# -------------------------------------------------------------
# PRESET TEMPLATES
# -------------------------------------------------------------

@router.get("/presets/list")
async def list_presets():
    """List saved mixing templates."""
    if not os.path.exists(PRESETS_FILE):
        return {"presets": [
            {
                "id": "cartoon_dub_master",
                "name": "🎬 Cartoon Dubbing Master",
                "description": "TIGER Sound Effects + External Voiceover + 150ms Hann Fades (Music Muted)",
                "models": ["tiger", "external"]
            },
            {
                "id": "film_sfx_focus",
                "name": "🎥 MSST Film SFX & Dialogue",
                "description": "MSST 14.84 SDR + TIGER Foley (Clean Action Track)",
                "models": ["roformer", "tiger"]
            }
        ]}
    with open(PRESETS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/presets/save")
async def save_preset(payload: SavePresetRequest):
    """Save a project configuration as a reusable template."""
    presets = []
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                presets = json.load(f).get("presets", [])
        except Exception:
            pass

    preset_id = str(uuid.uuid4())[:8]
    presets.append({
        "id": preset_id,
        "name": payload.name,
        "description": payload.description,
        "settings": payload.settings
    })

    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump({"presets": presets}, f, indent=2)

    return {"status": "saved", "preset_id": preset_id}
