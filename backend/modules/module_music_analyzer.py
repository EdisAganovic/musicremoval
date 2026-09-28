"""
MODULE: module_music_analyzer.py - AI Music Detection & SRT Timestamp Generator

ROLE: Analyzes audio/video files to detect where background music and soundtrack stems appear,
      respecting 30-minute chunk limits and 100MB prompt constraints, and produces standard SRT subtitle files.

WORKFLOW:
  1. Inspect file duration via FFprobe.
  2. Split long audio (>30 minutes) into <= 30-minute high-fidelity chunks (MP3/WAV <100MB).
  3. Send each chunk to Antigravity CLI (`agy --dangerously-skip-permissions -p "..."`) with multimodal audio prompt.
  4. Parse detected music intervals and adjust offsets (+1800s per chunk).
  5. Merge contiguous/overlapping music intervals.
  6. Generate standard .srt subtitle files and structured JSON cue sheets.
"""

import os
import sys
import json
import re
import subprocess
import shutil
import tempfile
import time
from typing import List, Dict, Any, Optional, Callable

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from module_ffmpeg import FFMPEG_EXE, FFPROBE_EXE, get_audio_duration
except ImportError:
    from modules.module_ffmpeg import FFMPEG_EXE, FFPROBE_EXE, get_audio_duration

MAX_CHUNK_DURATION_SECONDS = 1800  # 30 minutes optimal precision limit


def find_agy_executable() -> Optional[str]:
    """Locate the agy CLI executable on the system."""
    # Check default Windows AppData path
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = os.path.join(local_app_data, "agy", "bin", "agy.exe")
        if os.path.isfile(candidate):
            return candidate

    # Check user profile path
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidate = os.path.join(user_profile, "AppData", "Local", "agy", "bin", "agy.exe")
        if os.path.isfile(candidate):
            return candidate

    # Check PATH
    which_agy = shutil.which("agy") or shutil.which("agy.exe")
    if which_agy:
        return which_agy

    return None


def format_seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis -= 1000
    if secs >= 60:
        mins += 1
        secs -= 60
    if mins >= 60:
        hrs += 1
        mins -= 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def parse_timestamp_to_seconds(ts_str: Any) -> Optional[float]:
    """Parse string timestamp (HH:MM:SS.mmm or MM:SS or seconds float) to seconds float."""
    if ts_str is None:
        return None
    if isinstance(ts_str, (int, float)):
        return float(ts_str)

    s = str(ts_str).strip().replace(",", ".")
    # Match HH:MM:SS.mmm or MM:SS.mmm
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h, m, sec = parts
            return float(h) * 3600 + float(m) * 60 + float(sec)
        elif len(parts) == 2:
            m, sec = parts
            return float(m) * 60 + float(sec)
        elif len(parts) == 1:
            return float(parts[0])
    except Exception:
        pass
    return None


def split_audio_into_chunks(
    input_path: str,
    output_dir: str,
    chunk_duration: int = MAX_CHUNK_DURATION_SECONDS
) -> List[Dict[str, Any]]:
    """
    Splits an audio or video file into <= chunk_duration (30m) audio segments (192k MP3)
    to guarantee file size < 100MB and optimal token/acoustic resolution.
    """
    duration = get_audio_duration(input_path)
    if not duration or duration <= 0:
        # Fallback probe
        duration = 1800.0

    chunks = []
    ffmpeg_bin = FFMPEG_EXE or "ffmpeg"
    
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    num_chunks = max(1, int((duration + chunk_duration - 1) // chunk_duration))

    for idx in range(num_chunks):
        start_time = idx * chunk_duration
        current_chunk_duration = min(chunk_duration, duration - start_time)
        if current_chunk_duration <= 0.5:
            break

        chunk_filename = f"{base_name}_chunk_{idx:03d}.mp3"
        chunk_path = os.path.join(output_dir, chunk_filename)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(current_chunk_duration),
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            chunk_path
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True
            )
            chunks.append({
                "index": idx,
                "path": chunk_path,
                "start_offset": float(start_time),
                "duration": float(current_chunk_duration)
            })
        except Exception as e:
            print(f"[MusicAnalyzer] Error creating chunk {idx}: {e}")

    return chunks


def analyze_chunk_with_agy(
    agy_exe: str,
    chunk_path: str,
    start_offset: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Sends an audio chunk to Antigravity CLI and parses the resulting music timestamps.
    """
    abs_chunk_path = os.path.abspath(chunk_path)
    
    prompt = (
        f"Listen carefully to this audio file at: \"{abs_chunk_path}\".\n"
        "Your task: Detect and identify all intervals/timestamps where background music, "
        "instrumental score, theme songs, beats, or musical accompaniment appear.\n\n"
        "Instructions:\n"
        "1. Identify the exact start and end time of every music segment.\n"
        "2. Provide a brief description of the music style (e.g. 'Dramatic orchestral score', 'Acoustic guitar background', 'Upbeat electronic theme', 'Mellow ambient piano').\n"
        "3. Return ONLY a valid JSON array of objects. Do NOT include markdown codeblocks or extra conversational text.\n"
        "Schema:\n"
        "[\n"
        "  {\n"
        "    \"start_seconds\": 14.5,\n"
        "    \"end_seconds\": 85.0,\n"
        "    \"description\": \"Upbeat acoustic guitar background music\",\n"
        "    \"confidence\": \"high\"\n"
        "  }\n"
        "]\n"
        "If absolutely no music appears in the entire audio, return an empty array: []"
    )

    cmd = [
        agy_exe,
        "--dangerously-skip-permissions",
        "-p",
        prompt
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300
        )
        output = proc.stdout.strip()
        if not output:
            output = proc.stderr.strip()

        # Extract JSON array from output (handles raw array or ```json [...] ```)
        json_match = re.search(r"\[\s*\{.*\}\s*\]", output, re.DOTALL)
        raw_json = json_match.group(0) if json_match else output

        parsed = json.loads(raw_json)
        if not isinstance(parsed, list):
            return []

        results = []
        for item in parsed:
            start_sec = parse_timestamp_to_seconds(item.get("start_seconds") or item.get("start"))
            end_sec = parse_timestamp_to_seconds(item.get("end_seconds") or item.get("end"))

            if start_sec is not None and end_sec is not None and end_sec > start_sec:
                adj_start = start_sec + start_offset
                adj_end = end_sec + start_offset
                desc = item.get("description", "Background Music").strip()
                conf = item.get("confidence", "high").strip()

                results.append({
                    "start_seconds": round(adj_start, 2),
                    "end_seconds": round(adj_end, 2),
                    "start_srt": format_seconds_to_srt_time(adj_start),
                    "end_srt": format_seconds_to_srt_time(adj_end),
                    "duration_seconds": round(adj_end - adj_start, 2),
                    "description": desc,
                    "confidence": conf
                })
        return results
    except Exception as e:
        print(f"[MusicAnalyzer] Error analyzing chunk {chunk_path}: {e}")
        return []


def merge_music_intervals(intervals: List[Dict[str, Any]], max_gap_seconds: float = 2.0) -> List[Dict[str, Any]]:
    """
    Merges overlapping or adjacent music intervals (gap <= max_gap_seconds).
    """
    if not intervals:
        return []

    sorted_ints = sorted(intervals, key=lambda x: x["start_seconds"])
    merged = []
    
    current = sorted_ints[0].copy()
    
    for nxt in sorted_ints[1:]:
        if nxt["start_seconds"] <= current["end_seconds"] + max_gap_seconds:
            # Merge
            current["end_seconds"] = max(current["end_seconds"], nxt["end_seconds"])
            current["end_srt"] = format_seconds_to_srt_time(current["end_seconds"])
            current["duration_seconds"] = round(current["end_seconds"] - current["start_seconds"], 2)
            if nxt.get("description") and nxt["description"] not in current["description"]:
                current["description"] += f" / {nxt['description']}"
        else:
            merged.append(current)
            current = nxt.copy()
            
    merged.append(current)
    return merged


def generate_srt_content(events: List[Dict[str, Any]]) -> str:
    """Generates standard SRT file string from music event list."""
    lines = []
    for idx, event in enumerate(events, start=1):
        start_srt = event.get("start_srt") or format_seconds_to_srt_time(event["start_seconds"])
        end_srt = event.get("end_srt") or format_seconds_to_srt_time(event["end_seconds"])
        desc = event.get("description", "Background Music")
        
        lines.append(f"{idx}")
        lines.append(f"{start_srt} --> {end_srt}")
        lines.append(f"[Music: {desc}]")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def process_music_analysis(
    input_file: str,
    output_dir: Optional[str] = None,
    chunk_duration: int = MAX_CHUNK_DURATION_SECONDS,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Dict[str, Any]:
    """
    Full music analysis pipeline:
    1. Splits file into <= 30min chunks (<100MB).
    2. Runs Antigravity multimodal audio analysis on each chunk.
    3. Merges timeline and formats SRT & JSON.
    """
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    agy_exe = find_agy_executable()
    if not agy_exe:
        raise RuntimeError("Antigravity CLI ('agy.exe') was not found on this machine.")

    if not output_dir:
        output_dir = os.path.dirname(input_file) or "."
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    total_duration = get_audio_duration(input_file) or 0.0

    temp_dir = tempfile.mkdtemp(prefix="music_analyzer_")
    
    try:
        if progress_callback:
            progress_callback(10, "Extracting audio and splitting into 30m precision chunks...")

        chunks = split_audio_into_chunks(input_file, temp_dir, chunk_duration=chunk_duration)
        if not chunks:
            raise RuntimeError("Failed to split audio into chunks for analysis.")

        all_events = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            pct = int(20 + (i / total_chunks) * 65)
            step_desc = f"Analyzing chunk {i+1} of {total_chunks} ({chunk['duration']:.1f}s) with Antigravity AI..."
            if progress_callback:
                progress_callback(pct, step_desc)

            chunk_events = analyze_chunk_with_agy(
                agy_exe=agy_exe,
                chunk_path=chunk["path"],
                start_offset=chunk["start_offset"]
            )
            all_events.extend(chunk_events)

        if progress_callback:
            progress_callback(90, "Merging timestamps and formatting SRT subtitle...")

        merged_events = merge_music_intervals(all_events)
        srt_content = generate_srt_content(merged_events)

        # Save SRT file
        srt_filename = f"{base_name}_music.srt"
        srt_path = os.path.join(output_dir, srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # Save JSON cue sheet
        json_filename = f"{base_name}_music.json"
        json_path = os.path.join(output_dir, json_filename)
        
        total_music_duration = sum(e["duration_seconds"] for e in merged_events)
        music_percentage = round((total_music_duration / total_duration * 100), 1) if total_duration > 0 else 0.0

        summary = {
            "file_name": os.path.basename(input_file),
            "total_duration_seconds": round(total_duration, 2),
            "total_music_seconds": round(total_music_duration, 2),
            "music_percentage": music_percentage,
            "segment_count": len(merged_events),
            "chunks_analyzed": total_chunks,
            "chunk_limit_seconds": chunk_duration
        }

        output_data = {
            "summary": summary,
            "events": merged_events,
            "srt_path": srt_path,
            "json_path": json_path
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        if progress_callback:
            progress_callback(100, "Music analysis complete!")

        return {
            "status": "completed",
            "srt_path": srt_path,
            "srt_content": srt_content,
            "json_path": json_path,
            "summary": summary,
            "events": merged_events
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
