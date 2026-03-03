"""
MODULE: module_ffmpeg_shared.py - FFmpeg SHARED LIBRARIES for torchcodec/torchaudio

ROLE: Ensures FFmpeg shared DLLs (avcodec, avformat, avutil, etc.) are available
      on the system PATH so that torchcodec can load them at runtime.

WHY: Demucs uses torchaudio, which uses torchcodec internally. torchcodec needs
     FFmpeg shared libraries (.dll files) to encode/decode audio. The project's
     existing FFmpeg is a custom static build (for FDK-AAC support) that does NOT
     include DLLs. This module downloads a separate shared build specifically for
     torchcodec.

FLOW:
  1. Check if shared DLLs already exist on PATH (e.g. avcodec-62.dll)
  2. If not, check our local cache (ffmpeg_shared/ folder in project root)
  3. If not cached, download BtbN's shared build from GitHub
  4. Extract and add the bin/ folder to os.environ["PATH"]

IMPORTANT: This does NOT replace the project's custom FFmpeg binary (module_ffmpeg.py).
           The FFMPEG_EXE used for audio conversion is a separate static build.
"""
import os
import sys
import shutil
import zipfile
import subprocess
from typing import Optional
from colorama import Fore, Style

# Where we store the shared FFmpeg build locally
FFMPEG_SHARED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'ffmpeg_shared'))

# The specific DLLs that torchcodec needs (any one present = OK)
# These names change with FFmpeg major versions, so we check multiple patterns
REQUIRED_DLLS = [
    'avcodec-*.dll',
    'avformat-*.dll', 
    'avutil-*.dll',
]

# BtbN builds - stable, well-known, .zip format (no 7zip needed)
FFMPEG_SHARED_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"


def _find_dll_on_path(pattern: str) -> Optional[str]:
    """Check if a DLL matching the pattern exists anywhere on PATH."""
    import glob
    
    # Check system PATH directories
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for d in path_dirs:
        if os.path.isdir(d):
            matches = glob.glob(os.path.join(d, pattern))
            if matches:
                return matches[0]
    return None


def _find_shared_bin_dir() -> Optional[str]:
    """Find the bin/ directory inside our local ffmpeg_shared/ folder."""
    if not os.path.isdir(FFMPEG_SHARED_DIR):
        return None
    
    # The extracted folder is typically ffmpeg-master-latest-win64-gpl-shared/bin/
    for entry in os.listdir(FFMPEG_SHARED_DIR):
        bin_dir = os.path.join(FFMPEG_SHARED_DIR, entry, 'bin')
        if os.path.isdir(bin_dir):
            # Verify it actually has DLLs
            import glob
            if glob.glob(os.path.join(bin_dir, 'av*.dll')):
                return bin_dir
    
    # Maybe files are directly in ffmpeg_shared/bin/
    bin_dir = os.path.join(FFMPEG_SHARED_DIR, 'bin')
    if os.path.isdir(bin_dir):
        import glob
        if glob.glob(os.path.join(bin_dir, 'av*.dll')):
            return bin_dir
    
    return None


def _add_to_path(directory: str):
    """Add a directory to the current process PATH."""
    current_path = os.environ.get("PATH", "")
    if directory.lower() not in current_path.lower():
        os.environ["PATH"] = directory + os.pathsep + current_path
        print(f"  {Fore.GREEN}Added to PATH: {directory}{Style.RESET_ALL}")


def check_shared_dlls_available() -> bool:
    """Check if FFmpeg shared DLLs are available on PATH."""
    import glob
    for pattern in REQUIRED_DLLS:
        if not _find_dll_on_path(pattern):
            return False
    return True


def ensure_ffmpeg_shared() -> bool:
    """
    Ensures FFmpeg shared DLLs are available for torchcodec.
    
    Returns:
        bool: True if DLLs are available (or not needed), False on failure.
    """
    # Only needed on Windows
    if sys.platform != "win32":
        return True
    
    # Check if torchcodec is even installed
    try:
        import importlib.metadata
        importlib.metadata.version("torchcodec")
    except Exception:
        # torchcodec not installed, no need for shared DLLs
        return True

    print(f"\n{Fore.CYAN}[FFmpeg Shared] Checking shared DLLs for torchcodec...{Style.RESET_ALL}")

    # Step 1: Already on PATH?
    if check_shared_dlls_available():
        print(f"  {Fore.GREEN}✓ FFmpeg shared DLLs found on PATH{Style.RESET_ALL}")
        return True

    # Step 2: Check our local cache
    bin_dir = _find_shared_bin_dir()
    if bin_dir:
        print(f"  {Fore.GREEN}✓ Found cached shared build: {bin_dir}{Style.RESET_ALL}")
        _add_to_path(bin_dir)
        return True

    # Step 3: Download
    print(f"  {Fore.YELLOW}⚠ FFmpeg shared DLLs not found. Downloading...{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}This is a one-time download (~90MB) required for Demucs/torchaudio.{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}Your custom FFmpeg (with FDK-AAC) is NOT affected.{Style.RESET_ALL}")
    
    success = _download_and_extract_shared()
    if not success:
        print(f"  {Fore.RED}✗ Failed to download FFmpeg shared build.{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Manual fix: Download from {FFMPEG_SHARED_URL}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Extract to: {FFMPEG_SHARED_DIR}{Style.RESET_ALL}")
        return False

    # Add to PATH
    bin_dir = _find_shared_bin_dir()
    if bin_dir:
        _add_to_path(bin_dir)
        print(f"  {Fore.GREEN}✓ FFmpeg shared DLLs installed and activated{Style.RESET_ALL}")
        return True
    else:
        print(f"  {Fore.RED}✗ Downloaded but could not find bin/ directory{Style.RESET_ALL}")
        return False


def _download_and_extract_shared() -> bool:
    """Download and extract the FFmpeg shared build."""
    import requests
    import time

    os.makedirs(FFMPEG_SHARED_DIR, exist_ok=True)
    zip_path = os.path.join(FFMPEG_SHARED_DIR, "ffmpeg-shared.zip")

    try:
        # Download with progress
        print(f"  Downloading from BtbN GitHub releases...")
        print(f"  URL: {FFMPEG_SHARED_URL}")
        
        response = requests.get(FFMPEG_SHARED_URL, stream=True, timeout=120, 
                                allow_redirects=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        speed = downloaded / (1024 * 1024 * max(0.01, time.time() - start_time))
                        print(f"\r  Downloading: {pct:.0f}% ({downloaded / (1024*1024):.1f} / {total_size / (1024*1024):.0f} MB) @ {speed:.1f} MB/s", end="", flush=True)
        
        elapsed = time.time() - start_time
        print(f"\n  Download complete: {downloaded / (1024*1024):.1f} MB in {elapsed:.1f}s")
        
        # Verify it's a valid zip
        if not zipfile.is_zipfile(zip_path):
            print(f"  {Fore.RED}Downloaded file is not a valid ZIP archive{Style.RESET_ALL}")
            os.remove(zip_path)
            return False
        
        # Extract
        print(f"  Extracting to {FFMPEG_SHARED_DIR}...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(FFMPEG_SHARED_DIR)
        
        # Clean up the zip
        os.remove(zip_path)
        
        # Verify DLLs exist in the extracted folder
        bin_dir = _find_shared_bin_dir()
        if not bin_dir:
            print(f"  {Fore.RED}Extraction succeeded but no DLLs found in extracted files{Style.RESET_ALL}")
            return False
        
        # Count DLLs for confirmation
        import glob
        dll_count = len(glob.glob(os.path.join(bin_dir, '*.dll')))
        print(f"  {Fore.GREEN}✓ Extracted {dll_count} DLL files to {bin_dir}{Style.RESET_ALL}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"\n  {Fore.RED}Download failed: {e}{Style.RESET_ALL}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False
    except zipfile.BadZipFile:
        print(f"\n  {Fore.RED}Downloaded file is corrupted (bad zip){Style.RESET_ALL}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False
    except Exception as e:
        print(f"\n  {Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
        return False


def get_shared_ffmpeg_info() -> dict:
    """Get info about the shared FFmpeg installation (for diagnostics)."""
    import glob
    
    info = {
        "needed": False,
        "available": False,
        "source": None,
        "bin_dir": None,
        "dlls": [],
    }
    
    # Check if torchcodec needs it
    try:
        import importlib.metadata
        importlib.metadata.version("torchcodec")
        info["needed"] = True
    except Exception:
        return info
    
    # Check PATH
    if check_shared_dlls_available():
        info["available"] = True
        info["source"] = "system_path"
        # Find where
        for pattern in REQUIRED_DLLS:
            found = _find_dll_on_path(pattern)
            if found:
                info["bin_dir"] = os.path.dirname(found)
                break
    
    # Check local cache
    bin_dir = _find_shared_bin_dir()
    if bin_dir:
        info["available"] = True
        info["source"] = info.get("source") or "local_cache"
        info["bin_dir"] = bin_dir
        info["dlls"] = [f for f in os.listdir(bin_dir) if f.endswith('.dll')]
    
    return info
