"""
FastAPI Backend for DemucsPleeter - Main Entry Point.

This is the main entry point that imports and mounts all route modules.
The actual business logic is in the services/ and routes/ modules.
"""
import os
import sys
import signal

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add project root to sys.path so modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add modules folder to sys.path for inter-module imports
modules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules')
sys.path.insert(0, modules_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from colorama import init

# Initialize colorama
init(autoreset=True)

# Create FastAPI app
app = FastAPI(
    title="DemucsPleeter API",
    description="API for vocal separation and YouTube downloading",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and mount routes
from routes.downloads import router as downloads_router
from routes.separation import router as separation_router
from routes.library import router as library_router
from routes.notifications import router as notifications_router
from routes.diagnostics import router as diagnostics_router

app.include_router(downloads_router)
app.include_router(separation_router)
app.include_router(library_router)
app.include_router(notifications_router)
app.include_router(diagnostics_router)


# ============== Startup/Shutdown Events ==============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    from config import (
        init_data_directory, load_queue, load_notifications, load_metadata_cache,
        load_tasks_async, cleanup_metadata_cache, cleanup_temp_files, log_console,
        save_queue, save_notifications, save_metadata_cache, start_cleanup_scheduler
    )
    from colorama import Fore, Style

    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  DemucsPleeter Backend Starting...{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")

    # Kill any stale processes from previous crashes
    from services.process_manager import kill_stale_processes, cleanup_all_children
    kill_stale_processes()

    # Initialize data directory and create missing JSON files
    init_data_directory()

    # Ensure FFmpeg is present (custom static build for FDK-AAC)
    from modules.module_ffmpeg import download_ffmpeg
    download_ffmpeg()

    # Ensure FFmpeg shared DLLs are available for torchcodec/torchaudio (used by Demucs)
    from modules.module_ffmpeg_shared import ensure_ffmpeg_shared
    ensure_ffmpeg_shared()

    # Load persisted data
    load_queue()
    load_notifications()
    load_metadata_cache()
    await load_tasks_async()

    # Cleanup old data
    cleanup_metadata_cache()
    cleanup_temp_files()

    # Start background cleanup scheduler (runs every hour)
    await start_cleanup_scheduler(interval_seconds=3600)

    # Register signal handlers for graceful cleanup
    def _signal_handler(signum, frame):
        print(f"\n{Fore.YELLOW}Signal {signum} received, cleaning up...{Style.RESET_ALL}")
        cleanup_all_children(reason=f"signal {signum}")
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except (ValueError, OSError):
        # signal handlers can only be set in the main thread
        pass

    log_console("Backend started successfully", "success")

    print(f"\n{Fore.CYAN}API available at: http://localhost:5170{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Docs available at: http://localhost:5170/docs{Style.RESET_ALL}\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    from config import (
        save_tasks_async, save_metadata_cache, save_queue, save_notifications,
        log_console, stop_cleanup_scheduler
    )
    from colorama import Fore, Style

    log_console("Backend shutting down...", "info")
    
    # Kill all tracked child processes first
    from services.process_manager import cleanup_all_children
    cleanup_all_children(reason="app shutdown")
    
    # Stop background cleanup scheduler
    await stop_cleanup_scheduler()
    
    # Save all state
    await save_tasks_async()
    save_metadata_cache()
    save_queue()
    save_notifications()

    print(f"\n{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  DemucsPleeter Backend Stopped{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}\n")


# ============== Health Check ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "demucspleeter-backend"}


# ============== Main Entry Point ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5170)
