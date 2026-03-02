"""
FastAPI Backend for DemucsPleeter - Main Entry Point.

This is the main entry point that imports and mounts all route modules.
The actual business logic is in the services/ and routes/ modules.
"""
import os
import sys

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

app.include_router(downloads_router)
app.include_router(separation_router)
app.include_router(library_router)
app.include_router(notifications_router)


# ============== Startup/Shutdown Events ==============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    from config import (
        load_queue, load_notifications, load_metadata_cache,
        cleanup_metadata_cache, cleanup_temp_files, log_console
    )
    from colorama import Fore, Style
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  DemucsPleeter Backend Starting...{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
    
    # Load persisted data
    load_queue()
    load_notifications()
    load_metadata_cache()
    
    # Cleanup
    cleanup_metadata_cache()
    cleanup_temp_files()
    
    log_console("Backend started successfully", "success")
    
    print(f"\n{Fore.CYAN}API available at: http://localhost:5170{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Docs available at: http://localhost:5170/docs{Style.RESET_ALL}\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    from config import save_metadata_cache, log_console
    from colorama import Fore, Style
    
    log_console("Backend shutting down...", "info")
    save_metadata_cache()
    
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
