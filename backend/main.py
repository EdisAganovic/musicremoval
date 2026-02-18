import os
import sys
import uuid
import asyncio
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import json
import subprocess

# Add parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add modules directory to sys.path so that module_processor can import siblings
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules"))

from modules.module_processor import process_file
from modules.module_ffmpeg import get_file_metadata
from modules.module_deno import run_deno_script, deno_eval

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock task storage (use a DB or Redis for production)
tasks: Dict[str, dict] = {}
LIBRARY_FILE = "library.json"

def save_to_library(task_data):
    """Saves a completed task to the local JSON library ✨."""
    try:
        library = []
        if os.path.exists(LIBRARY_FILE) and os.path.getsize(LIBRARY_FILE) > 0:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                try:
                    library = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: {LIBRARY_FILE} was corrupted. Starting fresh.")
                    library = []
        
        # Add new task at the beginning if not already there (prevent duplicates)
        # Check if task_id already exists in library
        existing_ids = {t.get("task_id") for t in library if isinstance(t, dict)}
        if task_data.get("task_id") not in existing_ids:
            library.insert(0, task_data)
        
        # Limit library size to 100 items
        library = library[:100]
        
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=4)
    except Exception as e:
        print(f"Error saving to library: {e}")

def get_full_library():
    """Reads all completed tasks and prunes missing files 🧼."""
    if not os.path.exists(LIBRARY_FILE) or os.path.getsize(LIBRARY_FILE) == 0:
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            library = json.load(f)
            
        # Filter out items where the primary result file no longer exists
        valid_items = []
        changed = False
        for item in library:
            res_files = item.get("result_files", [])
            if res_files and os.path.exists(res_files[0]):
                valid_items.append(item)
            else:
                changed = True
        
        # If any items were removed, update the JSON file
        if changed:
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(valid_items, f, indent=4)
            return valid_items
            
        return library
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"Error reading library: {e}")
        return []

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    current_step: str
    result_files: List[str] = []
    metadata: dict = {}

@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

async def run_yt_dlp(task_id: str, url: str, format_type: str = 'audio', format_id: str = None):
    tasks[task_id] = {"task_id": task_id, "status": "processing", "progress": 0, "current_step": "Starting download", "result_files": []}
    
    output_dir = "download"
    os.makedirs(output_dir, exist_ok=True)
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%','')
            try:
                tasks[task_id]["progress"] = float(p.strip())
            except:
                pass
            tasks[task_id]["current_step"] = f"Downloading: {d.get('_percent_str', '0%')}"
        elif d['status'] == 'finished':
            tasks[task_id]["progress"] = 99
            tasks[task_id]["current_step"] = "Finalizing & Merging formats..."

    # Use selected format_id if provided, otherwise fallback to defaults
    if format_id:
        download_format = f"{format_id}+bestaudio/best" if format_type == 'video' else format_id
    else:
        download_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if format_type == 'video' else 'bestaudio/best'

    ydl_opts = {
        'format': download_format,
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'progress_hooks': [progress_hook],
        # Solve JS challenges (requires deno which we have!)
        'remote_components': ['ejs:github'],
        'quiet': True,
        'no_warnings': False,
    }
    
    if format_type == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info will blocks until download AND merging is finished
            info = ydl.extract_info(url, download=True)
            
            # Use the actual filename from info, which yt-dlp updates after merging/post-processing
            # Sometimes it's in requested_downloads, sometimes in _filename
            final_filename = info.get('_filename')
            
            # Safety check if filename is None
            if not final_filename:
                final_filename = ydl.prepare_filename(info)

            # If audio post-processor ran, the extension might need correction
            if format_type == 'audio' and final_filename and not final_filename.endswith('.mp3'):
                final_filename = os.path.splitext(final_filename)[0] + ".mp3"
            
            if final_filename and not os.path.exists(final_filename):
                 # Fallback logic if _filename isn't quite right
                 possible_name = ydl.prepare_filename(info)
                 if not os.path.exists(possible_name):
                     # Try to find it in the directory by title
                     title = info.get('title')
                     for f in os.listdir(output_dir):
                         if title in f and f.endswith(('.mp4', '.mp3', '.mkv', '.webm')):
                             final_filename = os.path.join(output_dir, f)
                             break
                 else:
                     final_filename = possible_name

            if not final_filename:
                raise Exception("Could not determine final download filename.")

            abs_path = os.path.abspath(final_filename)
            
            # Extract metadata for the library
            try:
                metadata = get_file_metadata(abs_path)
                tasks[task_id]["metadata"] = metadata
            except Exception as meta_err:
                print(f"Error extracting metadata: {meta_err}")
                tasks[task_id]["metadata"] = {"duration": "N/A", "resolution": "N/A", "audio_codec": "N/A", "video_codec": "N/A", "is_video": format_type == 'video'}

            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["result_files"] = [abs_path]
            tasks[task_id]["current_step"] = "Finished"
            
            # Final library save with the correct merged filename
            save_to_library(tasks[task_id])
            print(f"Download complete: {abs_path}")
            
    except Exception as e:
        print(f"Download error: {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Download error: {str(e)}"

@app.post("/api/yt-formats")
async def get_yt_formats(payload: dict):
    """Fetches available formats for a YouTube URL using yt-dlp -F logic ✨."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        ydl_opts = {
            'quiet': True, 
            'noplaylist': True,
            'remote_components': ['ejs:github']
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                # Filter for useful information
                format_info = {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "note": f.get("format_note"),
                    "filesize": f.get("filesize"),
                    "url": f.get("url") # sometimes needed
                }
                # Simplify labels
                label = f"{f.get('ext')} - {f.get('resolution')} ({f.get('format_note') or ''})"
                if f.get('vcodec') == 'none':
                    label = f"Audio: {f.get('ext')} ({f.get('format_note') or ''})"
                format_info["label"] = label
                formats.append(format_info)
            
            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "formats": formats
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download")
async def download_video(background_tasks: BackgroundTasks, payload: dict):
    url = payload.get("url")
    format_type = payload.get("format", "audio")
    format_id = payload.get("format_id")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_yt_dlp, task_id, url, format_type, format_id)
    return {"task_id": task_id}

async def run_separation(task_id: str, file_path: str):
    def progress_callback(step, progress):
        tasks[task_id]["current_step"] = step
        tasks[task_id]["progress"] = progress
        tasks[task_id]["status"] = "processing"

    try:
        # Run process_file in a thread since it's blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_file, file_path, False, None, progress_callback)
        
        if result and isinstance(result, str):
            abs_path = os.path.abspath(result)
            
            # Extract final metadata for the library
            try:
                metadata = get_file_metadata(abs_path)
                tasks[task_id]["metadata"] = metadata
            except Exception as meta_err:
                print(f"Error extracting separation metadata: {meta_err}")

            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Finished"
            tasks[task_id]["result_files"] = [abs_path]
            # Save to persistent library
            save_to_library(tasks[task_id])
        elif result is False:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Processing failed or aborted"
        else:
            # Fallback for unexpected return types
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Internal error: Invalid processing result"
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Error: {str(e)}"

@app.post("/api/separate")
async def separate_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    
    # Save uploaded file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract metadata
    metadata = get_file_metadata(file_path)
    
    tasks[task_id] = {
        "task_id": task_id, 
        "status": "pending", 
        "progress": 0, 
        "current_step": "File uploaded", 
        "result_files": [],
        "metadata": metadata
    }
    
    background_tasks.add_task(run_separation, task_id, file_path)
    
    return {"task_id": task_id, "metadata": metadata}

@app.get("/api/library")
async def get_library():
    """Returns a list of all completed tasks from the JSON file."""
    return get_full_library()

@app.post("/api/open-folder")
async def open_folder(payload: dict):
    """Opens the directory of a file in Windows Explorer."""
    path = payload.get("path")
    if not path or not os.path.exists(path):
        # Even if file is gone, try to open the parent directory
        if path:
            parent = os.path.dirname(path)
            if os.path.exists(parent):
                os.startfile(parent)
                return {"status": "opened_parent"}
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Open folder and select the file (non-blocking)
    try:
        norm_path = os.path.normpath(path)
        # Use Popen to not block the server, and shell=True for explorer
        subprocess.Popen(f'explorer /select,"{norm_path}"', shell=True)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error opening explorer: {e}")
        # Fallback to opening directory
        os.startfile(os.path.dirname(norm_path))
        return {"status": "opened_parent_fallback"}

@app.post("/api/open-file")
async def open_file(payload: dict):
    """Opens a file directly with the default system application 🎬."""
    path = payload.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fajl nije pronađen")
    
    try:
        os.startfile(os.path.normpath(path))
        return {"status": "ok"}
    except Exception as e:
        print(f"Error opening file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/deno-info")
async def get_deno_info():
    """Returns information from Deno runtime 🦖."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deno_hello.ts")
    return run_deno_script(script_path)

@app.post("/api/delete-file")
async def delete_file(payload: dict):
    """Deletes the result file from disk and removes it from the library 🗑️."""
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="Task ID is required")
    
    try:
        library = get_full_library()
        new_library = []
        file_to_delete = None
        
        for item in library:
            if item.get("task_id") == task_id:
                res_files = item.get("result_files", [])
                if res_files:
                    file_to_delete = res_files[0]
            else:
                new_library.append(item)
        
        # Delete from disk if found
        if file_to_delete and os.path.exists(file_to_delete):
            try:
                os.remove(file_to_delete)
                print(f"Deleted file: {file_to_delete}")
            except Exception as e:
                print(f"Error deleting file from disk: {e}")
        
        # Save updated library
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(new_library, f, indent=4)
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Error in delete_file endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Set log_level to "warning" to hide the spammy polling INFO logs
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
