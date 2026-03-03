"""
Diagnostics API Routes - System health checks for debugging Demucs/Spleeter issues.

Provides comprehensive diagnostics:
  - Python & package versions (torch, demucs, spleeter, torchaudio)
  - CUDA/GPU detection and details
  - FFmpeg availability 
  - Disk space on key directories
  - Model file presence check (pretrained_models/)
  - Test separation on a short audio snippet
  - System info (OS, CPU, RAM)

NOTE: All heavy operations (torch import, demucs import, nvidia-smi) run in
      a thread pool with individual timeouts so the endpoint never hangs.
"""
import os
import sys
import time
import shutil
import platform
import subprocess
import traceback
import tempfile
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from fastapi import APIRouter, BackgroundTasks
from typing import Optional

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

# Shared thread pool for diagnostics (avoids blocking the async loop)
_diag_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="diag")


def _run_with_timeout(fn, timeout=15):
    """Run a function in a thread with a timeout. Returns result or error dict."""
    import concurrent.futures
    future = _diag_pool.submit(fn)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return {"error": f"Timed out after {timeout}s", "timed_out": True}
    except Exception as e:
        return {"error": str(e)}


def _get_package_version(package_name: str) -> str:
    """Get installed package version or 'NOT INSTALLED'."""
    try:
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except Exception:
        return "NOT INSTALLED"


def _get_disk_space(path: str) -> dict:
    """Get disk space info for the given path."""
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 1),
        }
    except Exception as e:
        return {"path": path, "error": str(e)}


def _check_system():
    """Gather basic system info (fast, no heavy imports)."""
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "cpu_count": os.cpu_count(),
        "cwd": os.getcwd(),
    }
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / (1024**3), 2)
        info["ram_available_gb"] = round(mem.available / (1024**3), 2)
        info["ram_percent_used"] = mem.percent
    except ImportError:
        info["ram_info"] = "psutil not installed (install for RAM details)"
    return info


def _check_packages():
    """Get versions of key packages (fast, uses importlib.metadata)."""
    packages = [
        "torch", "torchaudio", "torchvision",
        "demucs", "spleeter",
        "numpy", "scipy", "soundfile",
        "yt-dlp", "fastapi", "uvicorn",
    ]
    return {pkg: _get_package_version(pkg) for pkg in packages}


def _check_cuda():
    """Check CUDA/GPU availability. This is the SLOW one (imports torch)."""
    cuda_info = {"available": False}
    try:
        import torch
        cuda_info["available"] = torch.cuda.is_available()
        cuda_info["torch_version"] = torch.__version__
        cuda_info["torch_cuda_version"] = getattr(torch.version, "cuda", None)
        try:
            cuda_info["cudnn_version"] = str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else None
            cuda_info["cudnn_enabled"] = torch.backends.cudnn.enabled
        except Exception:
            cuda_info["cudnn_version"] = None
            cuda_info["cudnn_enabled"] = False

        if torch.cuda.is_available():
            cuda_info["device_count"] = torch.cuda.device_count()
            cuda_info["devices"] = []
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                cuda_info["devices"].append({
                    "index": i,
                    "name": props.name,
                    "total_memory_gb": round(props.total_mem / (1024**3), 2),
                    "major": props.major,
                    "minor": props.minor,
                    "multi_processor_count": props.multi_processor_count,
                })
            cuda_info["memory_allocated_gb"] = round(torch.cuda.memory_allocated() / (1024**3), 3)
            cuda_info["memory_reserved_gb"] = round(torch.cuda.memory_reserved() / (1024**3), 3)
        else:
            cuda_info["reason"] = "torch.cuda.is_available() returned False"
            # Quick nvidia-smi check (5s timeout)
            try:
                nvidia_smi = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5
                )
                if nvidia_smi.returncode == 0:
                    cuda_info["nvidia_smi_output"] = nvidia_smi.stdout.strip()
                    cuda_info["hint"] = "GPU detected via nvidia-smi but PyTorch can't use it. Likely need to reinstall PyTorch with CUDA support."
                else:
                    cuda_info["nvidia_smi_error"] = nvidia_smi.stderr.strip()
            except FileNotFoundError:
                cuda_info["nvidia_smi"] = "nvidia-smi not found (no NVIDIA drivers?)"
            except subprocess.TimeoutExpired:
                cuda_info["nvidia_smi"] = "nvidia-smi timed out"
            except Exception as e:
                cuda_info["nvidia_smi_error"] = str(e)

    except ImportError:
        cuda_info["error"] = "PyTorch not installed"
    except Exception as e:
        cuda_info["error"] = str(e)

    return cuda_info


def _check_ffmpeg():
    """Check FFmpeg binary."""
    ffmpeg_info = {}
    try:
        from modules.module_ffmpeg import FFMPEG_EXE
        ffmpeg_info["path"] = FFMPEG_EXE
        ffmpeg_info["exists"] = os.path.exists(FFMPEG_EXE)
        if os.path.exists(FFMPEG_EXE):
            result = subprocess.run([FFMPEG_EXE, "-version"], capture_output=True, text=True, timeout=5)
            first_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            ffmpeg_info["version"] = first_line
        else:
            ffmpeg_info["error"] = "FFmpeg binary not found at expected path"
    except Exception as e:
        ffmpeg_info["error"] = str(e)
    return ffmpeg_info


def _check_demucs_import():
    """Try importing demucs (can be slow)."""
    demucs_import = {}
    try:
        import demucs
        demucs_import["importable"] = True
        demucs_import["location"] = os.path.dirname(demucs.__file__)
    except ImportError as e:
        demucs_import["importable"] = False
        demucs_import["error"] = str(e)
    except Exception as e:
        demucs_import["importable"] = False
        demucs_import["error"] = str(e)

    try:
        import demucs.separate
        demucs_import["separate_importable"] = True
    except Exception as e:
        demucs_import["separate_importable"] = False
        demucs_import["separate_error"] = str(e)

    return demucs_import


def _check_disk_and_dirs():
    """Check disk space and key directories (fast)."""
    disk = {
        "project_root": _get_disk_space(os.getcwd()),
        "download_dir": _get_disk_space(os.path.join(os.getcwd(), "download")),
        "nomusic_dir": _get_disk_space(os.path.join(os.getcwd(), "nomusic")),
        "temp_dir": _get_disk_space(tempfile.gettempdir()),
    }

    key_dirs = {
        "download": os.path.join(os.getcwd(), "download"),
        "nomusic": os.path.join(os.getcwd(), "nomusic"),
        "uploads": os.path.join(os.getcwd(), "uploads"),
        "_temp": os.path.join(os.getcwd(), "_temp"),
        "_processing_intermediates": os.path.join(os.getcwd(), "_processing_intermediates"),
        "data": os.path.join(os.getcwd(), "data"),
    }
    directories = {}
    for name, path in key_dirs.items():
        exists = os.path.isdir(path)
        file_count = 0
        if exists:
            try:
                file_count = len(os.listdir(path))
            except Exception:
                pass
        directories[name] = {
            "path": path,
            "exists": exists,
            "file_count": file_count,
        }

    return {"disk": disk, "directories": directories}


def _check_models():
    """Check model files."""
    models_info = {}
    pretrained_dir = os.path.join(os.getcwd(), "pretrained_models")
    models_info["pretrained_dir_exists"] = os.path.isdir(pretrained_dir)
    if os.path.isdir(pretrained_dir):
        model_files = []
        for root, dirs, files in os.walk(pretrained_dir):
            for f in files:
                fpath = os.path.join(root, f)
                model_files.append({
                    "path": os.path.relpath(fpath, pretrained_dir),
                    "size_mb": round(os.path.getsize(fpath) / (1024**2), 2)
                })
        models_info["files"] = model_files
        models_info["total_files"] = len(model_files)
    else:
        models_info["files"] = []
        models_info["total_files"] = 0

    torch_hub_dir = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints")
    models_info["torch_hub_cache"] = torch_hub_dir
    models_info["torch_hub_exists"] = os.path.isdir(torch_hub_dir)
    if os.path.isdir(torch_hub_dir):
        hub_files = []
        for f in os.listdir(torch_hub_dir):
            fpath = os.path.join(torch_hub_dir, f)
            if os.path.isfile(fpath):
                hub_files.append({
                    "name": f,
                    "size_mb": round(os.path.getsize(fpath) / (1024**2), 2)
                })
        models_info["hub_files"] = hub_files
    else:
        models_info["hub_files"] = []

    return models_info


@router.get("/health")
async def full_health_check():
    """
    Comprehensive system health check.
    Each section runs in a thread pool with individual timeouts
    so a slow import (torch/demucs) doesn't block everything.
    """
    loop = asyncio.get_event_loop()
    results = {}

    # Fast checks - run directly (no heavy imports)
    results["system"] = _check_system()
    results["packages"] = _check_packages()

    disk_dirs = _check_disk_and_dirs()
    results["disk"] = disk_dirs["disk"]
    results["directories"] = disk_dirs["directories"]

    # Heavy checks - run in thread pool with timeouts
    # These run concurrently for speed
    cuda_future = loop.run_in_executor(_diag_pool, _check_cuda)
    ffmpeg_future = loop.run_in_executor(_diag_pool, _check_ffmpeg)

    # CUDA check with 20s timeout (importing torch can be slow)
    try:
        results["cuda"] = await asyncio.wait_for(cuda_future, timeout=20)
    except asyncio.TimeoutError:
        results["cuda"] = {
            "available": False,
            "error": "CUDA check timed out after 20s (torch import is very slow on this machine)",
            "timed_out": True,
        }

    # FFmpeg check with 10s timeout
    try:
        results["ffmpeg"] = await asyncio.wait_for(ffmpeg_future, timeout=10)
    except asyncio.TimeoutError:
        results["ffmpeg"] = {"error": "FFmpeg check timed out after 10s", "timed_out": True}

    # Model files (fast, filesystem only)
    results["models"] = _check_models()

    # Demucs import test with 20s timeout
    demucs_future = loop.run_in_executor(_diag_pool, _check_demucs_import)
    try:
        results["demucs_import"] = await asyncio.wait_for(demucs_future, timeout=20)
    except asyncio.TimeoutError:
        results["demucs_import"] = {
            "importable": False,
            "error": "Demucs import timed out after 20s",
            "timed_out": True,
            "separate_importable": False,
        }

    return results


@router.post("/test-demucs")
async def test_demucs(background_tasks: BackgroundTasks):
    """
    Run a quick Demucs test on a generated 5-second sine wave.
    Returns a task_id that you can poll via /api/diagnostics/test-status/<task_id>.
    """
    task_id = f"diag-{uuid.uuid4()}"

    from config import tasks
    tasks[task_id] = {
        "task_id": task_id,
        "type": "diagnostic",
        "status": "running",
        "progress": 0,
        "current_step": "Generating test audio...",
        "result": None,
        "error": None,
        "started_at": time.time(),
    }

    background_tasks.add_task(_run_demucs_test, task_id)
    return {"task_id": task_id, "status": "started"}


def _run_demucs_test(task_id: str):
    """Background task: generate a short tone and run Demucs on it."""
    from config import tasks

    test_dir = None
    try:
        # Step 1: Generate 5-second test WAV
        tasks[task_id]["current_step"] = "Generating 5-second test audio..."
        tasks[task_id]["progress"] = 10

        test_dir = tempfile.mkdtemp(prefix="demucs_test_")
        test_wav = os.path.join(test_dir, "test_tone.wav")

        # Use FFmpeg to generate a sine wave
        try:
            from modules.module_ffmpeg import FFMPEG_EXE
            ffmpeg_cmd = [
                FFMPEG_EXE, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                "-ar", "44100", "-ac", "2",
                test_wav
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")
        except Exception as e:
            # Fallback: generate WAV with numpy
            tasks[task_id]["current_step"] = "FFmpeg unavailable, generating test WAV with numpy..."
            import numpy as np
            import soundfile as sf
            sr = 44100
            t = np.linspace(0, 5, sr * 5, endpoint=False)
            tone = 0.5 * np.sin(2 * np.pi * 440 * t)
            audio = np.column_stack([tone, tone])  # stereo
            sf.write(test_wav, audio, sr)

        if not os.path.exists(test_wav):
            raise Exception("Failed to create test audio file")

        file_size = os.path.getsize(test_wav)
        tasks[task_id]["current_step"] = f"Test audio created ({file_size / 1024:.0f} KB)"
        tasks[task_id]["progress"] = 25

        # Step 2: Run Demucs separation
        tasks[task_id]["current_step"] = "Running Demucs htdemucs model..."
        tasks[task_id]["progress"] = 30

        demucs_out = os.path.join(test_dir, "demucs_output")
        os.makedirs(demucs_out, exist_ok=True)

        start_time = time.time()

        demucs_cmd = [
            sys.executable, "-m", "demucs.separate",
            "-n", "htdemucs",
            "-o", demucs_out,
            test_wav
        ]

        tasks[task_id]["current_step"] = f"Running: {' '.join(demucs_cmd)}"
        tasks[task_id]["progress"] = 40

        proc = subprocess.run(
            demucs_cmd,
            capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace'
        )

        elapsed = time.time() - start_time
        tasks[task_id]["progress"] = 90

        if proc.returncode != 0:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["current_step"] = "Demucs failed"
            tasks[task_id]["error"] = proc.stderr[-2000:] if proc.stderr else "Unknown error"
            tasks[task_id]["result"] = {
                "success": False,
                "returncode": proc.returncode,
                "stderr": proc.stderr[-2000:] if proc.stderr else "",
                "stdout": proc.stdout[-1000:] if proc.stdout else "",
                "elapsed_seconds": round(elapsed, 2),
                "command": " ".join(demucs_cmd),
            }
            return

        # Step 3: Verify output
        tasks[task_id]["current_step"] = "Verifying output files..."
        vocal_path = os.path.join(demucs_out, "htdemucs", "test_tone", "vocals.wav")
        expected_stems = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]
        stems_dir = os.path.join(demucs_out, "htdemucs", "test_tone")

        found_stems = {}
        if os.path.isdir(stems_dir):
            for stem in expected_stems:
                stem_path = os.path.join(stems_dir, stem)
                if os.path.exists(stem_path):
                    found_stems[stem] = {
                        "exists": True,
                        "size_kb": round(os.path.getsize(stem_path) / 1024, 1),
                    }
                else:
                    found_stems[stem] = {"exists": False}
        else:
            # List what we actually got
            for root, dirs, files in os.walk(demucs_out):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), demucs_out)
                    found_stems[rel] = {
                        "exists": True,
                        "size_kb": round(os.path.getsize(os.path.join(root, f)) / 1024, 1),
                    }

        # Check CUDA usage during the run
        cuda_used = "unknown"
        try:
            import torch
            cuda_used = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
        except Exception:
            pass

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["current_step"] = "Test completed successfully"
        tasks[task_id]["result"] = {
            "success": True,
            "elapsed_seconds": round(elapsed, 2),
            "device": cuda_used,
            "stems_found": found_stems,
            "all_stems_present": all(
                found_stems.get(s, {}).get("exists", False) for s in expected_stems
            ),
            "command": " ".join(demucs_cmd),
            "stdout": proc.stdout[-500:] if proc.stdout else "",
        }

    except subprocess.TimeoutExpired:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = "Demucs test timed out (>5 min)"
        tasks[task_id]["error"] = "Demucs took more than 5 minutes on a 5-second file. This indicates a serious performance problem."
        tasks[task_id]["result"] = {"success": False, "error": "timeout"}

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["current_step"] = f"Test failed: {str(e)[:100]}"
        tasks[task_id]["error"] = traceback.format_exc()
        tasks[task_id]["result"] = {"success": False, "error": str(e)}

    finally:
        # Cleanup test directory
        if test_dir and os.path.isdir(test_dir):
            try:
                shutil.rmtree(test_dir)
            except Exception:
                pass


@router.get("/test-status/{task_id}")
async def get_test_status(task_id: str):
    """Poll the status of a diagnostic test."""
    from config import tasks
    if task_id not in tasks:
        return {"error": "Test not found", "task_id": task_id}
    return tasks[task_id]
