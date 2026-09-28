"""
API ROUTES: music_analyzer.py - AI Music Detection & SRT Subtitle Generator

Endpoints:
  - POST /api/music-analyzer/analyze (Direct upload or library file path)
  - GET  /api/music-analyzer/status/{task_id} (Task progress polling)
  - GET  /api/music-analyzer/download-srt/{task_id} (Download .srt file)
"""

import os
import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import tasks, add_notification, log_console
from core.constants import NOMUSIC_DIR
from modules.module_music_analyzer import process_music_analysis, MAX_CHUNK_DURATION_SECONDS

router = APIRouter(prefix="/api/music-analyzer", tags=["music-analyzer"])


class MusicAnalyzeRequest(BaseModel):
    file_path: str
    chunk_duration: Optional[int] = MAX_CHUNK_DURATION_SECONDS


def run_music_analysis_task(task_id: str, file_path: str, chunk_duration: int):
    """Background worker for Music Analyzer."""
    try:
        def update_progress(pct: int, step_desc: str):
            if task_id in tasks:
                tasks[task_id]["progress"] = pct
                tasks[task_id]["current_step"] = step_desc
                tasks[task_id]["status"] = "processing"

        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 5
        tasks[task_id]["current_step"] = "Initializing Antigravity Music Analyzer..."

        result = process_music_analysis(
            input_file=file_path,
            output_dir=NOMUSIC_DIR,
            chunk_duration=chunk_duration,
            progress_callback=update_progress
        )

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["current_step"] = "Music analysis completed!"
        tasks[task_id]["result"] = result
        tasks[task_id]["srt_path"] = result.get("srt_path")
        tasks[task_id]["srt_content"] = result.get("srt_content")
        tasks[task_id]["summary"] = result.get("summary")
        tasks[task_id]["events"] = result.get("events")

        add_notification(
            title="Music Analysis Complete",
            message=f"Generated music SRT for {os.path.basename(file_path)} with {result['summary']['segment_count']} segments.",
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
            title="Music Analysis Failed",
            message=f"Failed to analyze music in {os.path.basename(file_path)}: {str(e)}",
            type="error"
        )


@router.post("/analyze")
async def start_music_analysis(
    background_tasks: BackgroundTasks,
    file_path: Optional[str] = Form(None),
    chunk_duration: int = Form(MAX_CHUNK_DURATION_SECONDS),
    file: Optional[UploadFile] = File(None)
):
    """Start analyzing an audio/video file to detect music timestamps."""
    target_file = None

    if file:
        # Save uploaded file to temp/downloads
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
        "file_path": target_file
    }

    background_tasks.add_task(
        run_music_analysis_task,
        task_id=task_id,
        file_path=target_file,
        chunk_duration=chunk_duration
    )

    return {
        "success": True,
        "task_id": task_id,
        "message": "Music analysis started"
    }


@router.get("/status/{task_id}")
async def get_music_analysis_status(task_id: str):
    """Retrieve status, progress, and results of music analysis."""
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
