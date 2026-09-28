"""
API ROUTES: music_analyzer.py - AI Music & Speech Sharia Compliance Analyzer

Endpoints:
  - POST /api/music-analyzer/analyze (Direct upload or library file path with mode, custom prompt & keywords)
  - GET  /api/music-analyzer/status/{task_id} (Task progress polling)
  - GET  /api/music-analyzer/download-srt/{task_id} (Download .srt file)
  - POST /api/music-analyzer/auto-censor (Mute/censor all flagged timestamps via FFmpeg)
  - GET  /api/music-analyzer/download-censored/{task_id} (Download clean censored media file)
"""

import os
import uuid
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import tasks, add_notification, log_console
from core.constants import NOMUSIC_DIR
from modules.module_music_analyzer import (
    process_music_analysis,
    auto_censor_media,
    MAX_CHUNK_DURATION_SECONDS
)

router = APIRouter(prefix="/api/music-analyzer", tags=["music-analyzer"])


class MusicAnalyzeRequest(BaseModel):
    file_path: str
    chunk_duration: Optional[int] = MAX_CHUNK_DURATION_SECONDS
    analysis_mode: Optional[str] = "music"
    custom_prompt: Optional[str] = None
    keywords: Optional[str] = None


class AutoCensorRequest(BaseModel):
    task_id: str


def run_music_analysis_task(
    task_id: str,
    file_path: str,
    chunk_duration: int,
    analysis_mode: str = "music",
    custom_prompt: Optional[str] = None,
    keywords: Optional[str] = None
):
    """Background worker for Audio & Speech Analyzer."""
    try:
        def update_progress(pct: int, step_desc: str):
            if task_id in tasks:
                tasks[task_id]["progress"] = pct
                tasks[task_id]["current_step"] = step_desc
                tasks[task_id]["status"] = "processing"

        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 5
        tasks[task_id]["current_step"] = "Initializing Antigravity Analyzer..."

        result = process_music_analysis(
            input_file=file_path,
            output_dir=NOMUSIC_DIR,
            chunk_duration=chunk_duration,
            analysis_mode=analysis_mode,
            custom_prompt=custom_prompt,
            keywords=keywords,
            progress_callback=update_progress
        )

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["current_step"] = "Analysis completed!"
        tasks[task_id]["result"] = result
        tasks[task_id]["srt_path"] = result.get("srt_path")
        tasks[task_id]["srt_content"] = result.get("srt_content")
        tasks[task_id]["summary"] = result.get("summary")
        tasks[task_id]["events"] = result.get("events")
        tasks[task_id]["analysis_mode"] = analysis_mode

        title_tag = "Sharia Speech Audit" if analysis_mode == "sharia_compliance" else "Speech Audit" if analysis_mode == "custom_speech" else "Music Analysis"
        add_notification(
            title=f"{title_tag} Complete",
            message=f"Generated SRT for {os.path.basename(file_path)} with {result['summary']['segment_count']} segments.",
            type="success"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        if task_id in tasks:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            tasks[task_id]["current_step"] = f"Error: {str(e)}"
        
        add_notification(
            title="Analysis Failed",
            message=f"Failed to analyze {os.path.basename(file_path)}: {str(e)}",
            type="error"
        )


@router.post("/analyze")
async def start_music_analysis(
    background_tasks: BackgroundTasks,
    file_path: Optional[str] = Form(None),
    chunk_duration: int = Form(MAX_CHUNK_DURATION_SECONDS),
    analysis_mode: str = Form("music"),
    custom_prompt: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """Start analyzing an audio/video file for music detection or speech compliance."""
    target_file = None

    if file:
        os.makedirs(NOMUSIC_DIR, exist_ok=True)
        safe_name = os.path.basename(file.filename or "upload.mp3")
        target_file = os.path.join(NOMUSIC_DIR, f"temp_analyzer_{uuid.uuid4().hex[:8]}_{safe_name}")
        with open(target_file, "wb") as f:
            content = await file.read()
            f.write(content)
    elif file_path:
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")
        target_file = file_path
    else:
        raise HTTPException(status_code=400, detail="Must provide either file upload or file_path")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "current_step": "Queued for analysis...",
        "file_name": os.path.basename(target_file),
        "file_path": target_file,
        "analysis_mode": analysis_mode,
        "keywords": keywords or ""
    }

    background_tasks.add_task(
        run_music_analysis_task,
        task_id=task_id,
        file_path=target_file,
        chunk_duration=chunk_duration,
        analysis_mode=analysis_mode,
        custom_prompt=custom_prompt,
        keywords=keywords
    )

    return {
        "success": True,
        "task_id": task_id,
        "analysis_mode": analysis_mode,
        "message": "Analysis started"
    }


@router.get("/status/{task_id}")
async def get_music_analysis_status(task_id: str):
    """Retrieve status, progress, and results of analysis."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/download-srt/{task_id}")
async def download_analysis_srt(task_id: str):
    """Download generated .srt subtitle file."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    srt_path = task.get("srt_path")
    if not srt_path or not os.path.isfile(srt_path):
        raise HTTPException(status_code=404, detail="SRT file not found or not yet generated")

    filename = os.path.basename(srt_path)
    return FileResponse(
        path=srt_path,
        media_type="text/plain",
        filename=filename
    )


@router.post("/auto-censor")
async def auto_censor_endpoint(request: AutoCensorRequest):
    """Mute all flagged timestamps using FFmpeg and generate a clean censored media file."""
    task = tasks.get(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    file_path = task.get("file_path")
    events = task.get("events") or []

    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Original media file not found")

    try:
        censored_path = auto_censor_media(
            input_file=file_path,
            intervals=events,
            output_dir=NOMUSIC_DIR
        )
        task["censored_file"] = censored_path

        return {
            "success": True,
            "censored_file": censored_path,
            "filename": os.path.basename(censored_path),
            "muted_count": len(events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-censor media: {str(e)}")


@router.get("/download-censored/{task_id}")
async def download_censored_media(task_id: str):
    """Download the auto-censored media file."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    censored_path = task.get("censored_file")
    if not censored_path or not os.path.isfile(censored_path):
        raise HTTPException(status_code=404, detail="Censored media file not generated yet")

    filename = os.path.basename(censored_path)
    return FileResponse(
        path=censored_path,
        filename=filename
    )
