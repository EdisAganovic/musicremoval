"""
MODULE: module_ytdlp.py - YouTube DOWNLOADER

ROLE: Downloads videos from YouTube using yt-dlp

RESPONSIBILITIES:
  - Auto-updates yt-dlp before each download
  - Sanitizes filenames for Windows compatibility
  - Handles format selection with fallback logic
  - Detects existing downloads to avoid duplicates
  - Supports cookies for age-restricted content
  - Handles playlist detection and processing

KEY FUNCTIONS:
  download_video(url, filename, cookies_file, is_playlist) → str | None
    - Returns path to downloaded file, None on failure
  check_and_update_ytdlp() → bool
    - Updates yt-dlp via uv pip
  sanitize_filename(filename, max_length) → str
    - Removes invalid chars, limits length to 200
  is_playlist_url(url) → bool
    - Detects if URL is a playlist

DOWNLOAD FLOW:
  1. Check/update yt-dlp
  2. Detect if playlist URL
  3. Get final filename via --get-filename
  4. Check for existing download (skip if found)
  5. Attempt best format (mp4+m4a)
  6. Fallback to alternative format if needed
  7. Return final file path

OUTPUT:
  - Saves to ./downloads/ folder
  - Auto-generates filename if not provided (limits title to 100 chars)

DEPENDENCIES:
  - module_ffmpeg.get_video_resolution(): For displaying video info
"""
import subprocess
import sys
import os
import re
import time
from colorama import Fore, Style
from module_ffmpeg import get_video_resolution


def is_playlist_url(url):
    """
    Detects if a URL is a YouTube playlist.
    
    Returns:
        bool: True if URL contains playlist indicators
    """
    playlist_indicators = [
        '/playlist?',
        'list=PL',
        'list=UU',
        'list=RD',
        'list=LL',
        '/watch?v=', # Single video (not playlist)
    ]
    
    # Check if it's a playlist URL
    if '/playlist?' in url or ('list=' in url and 'list=PL' in url or 'list=UU' in url or 'list=RD' in url or 'list=LL' in url):
        return True
    
    # Check for channel uploads/mixes
    if any(indicator in url for indicator in ['/channel/', '/@', '/c/']):
        # Could be a channel URL - treat as potential playlist
        return False
    
    return False


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitizes a filename by removing invalid characters and limiting length.
    Also prevents path traversal attacks.

    Args:
        filename: The original filename to sanitize
        max_length: Maximum length for the filename (default 200)

    Returns:
        Sanitized filename that's safe for the filesystem
    """
    # SECURITY: Remove path traversal attempts
    filename = filename.replace('..', '_')
    
    # SECURITY: Only keep the basename (prevent directory traversal)
    filename = os.path.basename(filename)
    
    # Replace invalid characters for Windows filesystem
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Remove leading/trailing spaces and dots which are invalid on Windows
    sanitized = sanitized.strip(' .')

    # Limit the length of the filename, preserving the extension
    name, ext = os.path.splitext(sanitized)
    if len(sanitized) > max_length:
        # Truncate the name part to fit within max_length, keeping extension
        max_name_length = max_length - len(ext)
        name = name[:max_name_length]
        sanitized = name + ext

    return sanitized

def check_and_update_ytdlp():
    """
    Checks for yt-dlp updates and installs or upgrades it.
    """
    print(f"{Fore.CYAN}Checking for yt-dlp updates...{Style.RESET_ALL}")
    try:
        # Get current yt-dlp version
        version_cmd = ["yt-dlp", "--version"]
        try:
            version_result = subprocess.run(version_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            print(f"{Fore.CYAN}Current yt-dlp version: {version_result.stdout.strip()}{Style.RESET_ALL}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"{Fore.YELLOW}yt-dlp not found or no version information available.{Style.RESET_ALL}")

        # Use UV to upgrade yt-dlp.
        update_cmd = ["uv", "pip", "install", "--upgrade", "yt-dlp"]
        print(f"{Fore.MAGENTA}Executing: {' '.join(update_cmd)}{Style.RESET_ALL}")
        result = subprocess.run(update_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if "Requirement already satisfied" in result.stdout:
            print(f"{Fore.GREEN}yt-dlp is up to date.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}yt-dlp has been installed/updated successfully.{Style.RESET_ALL}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error updating yt-dlp: {e}\n{e.stderr}{Style.RESET_ALL}")
        return False

def download_video(url, filename=None, cookies_file=None):
    """
    Downloads a video from a URL using yt-dlp into a 'download' folder.
    Returns the path to the downloaded file.
    """
    url = url.split('&')[0]
    if not check_and_update_ytdlp():
        return None

    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)

    try:
        # 1. Get the final filename from yt-dlp before downloading
        if filename:
            # Sanitize the provided filename to ensure it's safe for the filesystem
            safe_filename = sanitize_filename(filename)
            output_template = os.path.join(download_folder, safe_filename)
        else:
            # Use a custom format that limits title length to prevent filesystem errors
            # Windows has a 260 character path limit by default, so we limit the title
            # yt-dlp format: %(title).Ns where N is the max number of characters
            output_template = os.path.join(download_folder, "%(title).100s.%(ext)s")

        get_filename_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--get-filename",
            "--ignore-errors",
            "--fragment-retries", "infinite",
            "--retry-sleep", "fragment:exp=1:300",
            "--extractor-args", "youtube:player_client=default,ios",
            "--remote-components", "ejs:github",
            "-o", output_template,
        ]
        if cookies_file and os.path.exists(cookies_file):
            print(f"{Fore.CYAN}Using cookies from: {cookies_file}{Style.RESET_ALL}")
            get_filename_cmd.extend(["--cookies", cookies_file])
        get_filename_cmd.append(url)

        print(f"{Fore.MAGENTA}Determining filename...{Style.RESET_ALL}")
        result = subprocess.run(get_filename_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode != 0:
            print(f"\n{Fore.RED}An error occurred while trying to get video metadata (Exit Code: {result.returncode}).{Style.RESET_ALL}")
            if result.stderr:
                print(f"{Fore.RED}{result.stderr.strip()}{Style.RESET_ALL}")

            # --- List available formats on metadata error ---
            print(f"\n{Fore.CYAN}--- Listing available formats for {url} ---")
            list_formats_cmd = [
                sys.executable, "-m", "yt_dlp", "-F", "--remote-components", "ejs:github", url
            ]
            if cookies_file and os.path.exists(cookies_file):
                list_formats_cmd.extend(["--cookies", cookies_file])
            
            list_result = subprocess.run(list_formats_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if list_result.stdout:
                print(list_result.stdout)
            if list_result.stderr:
                print(f"{Fore.RED}{list_result.stderr.strip()}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}--- End of available formats ---")
            return None

        final_filepath = result.stdout.strip().splitlines()[-1]
        filename_without_ext, _ = os.path.splitext(os.path.basename(final_filepath))

        for f in os.listdir(download_folder):
            f_without_ext, _ = os.path.splitext(f)
            if f_without_ext == filename_without_ext:
                existing_filepath = os.path.join(download_folder, f)
                file_size = os.path.getsize(existing_filepath) / (1024 * 1024)
                resolution = get_video_resolution(existing_filepath)
                print(f"\n{Fore.YELLOW}Video with the same base name already exists.{Style.RESET_ALL}")
                print(f"  - File: {existing_filepath}")
                print(f"  - Size: {file_size:.2f} MB")
                if resolution:
                    print(f"  - Resolution: {resolution}px")
                print("Skipping download.")
                return existing_filepath

        print(f"{Fore.CYAN}Downloading to '{final_filepath}'...{Style.RESET_ALL}")

        base_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--ignore-errors",
            "--fragment-retries", "infinite",
            "--retry-sleep", "fragment:exp=1:300",
            "--remote-components", "ejs:github",
            "-o", output_template,
        ]
        
        format_attempts = [
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        ]

        download_successful = False
        for i, format_str in enumerate(format_attempts):
            print(f"{Fore.CYAN}Attempt {i+1}: Trying format '{format_str}'...{Style.RESET_ALL}")

            download_cmd = base_cmd + ["-f", format_str]
            if cookies_file and os.path.exists(cookies_file):
                download_cmd.extend(["--cookies", cookies_file])
            download_cmd.append(url)

            files_before_attempt = set(os.listdir(download_folder))
            
            # FIX: Capture output for debugging instead of swallowing errors
            result = subprocess.run(download_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                print(f"{Fore.RED}Download attempt failed: {result.stderr[:500]}{Style.RESET_ALL}")
                # Add backoff delay before next attempt
                if i < len(format_attempts) - 1:
                    print(f"{Fore.YELLOW}Waiting 2 seconds before retry...{Style.RESET_ALL}")
                    time.sleep(2)

            # First, check for the exact filename we expected
            if os.path.exists(final_filepath) and os.path.getsize(final_filepath) > 0:
                download_successful = True
                break

            # If that failed, check for any new, non-temporary file in the download folder
            files_after_attempt = set(os.listdir(download_folder))
            new_files = files_after_attempt - files_before_attempt

            for f in new_files:
                if not f.endswith('.part'):
                    path = os.path.join(download_folder, f)
                    if os.path.isfile(path) and os.path.getsize(path) > 0:
                        final_filepath = path  # Update to the actual downloaded file path
                        download_successful = True
                        break

            if download_successful:
                break

            if i < len(format_attempts) - 1:
                print(f"\n{Fore.YELLOW}Attempt {i+1} failed. Trying next format...{Style.RESET_ALL}")

        if download_successful:
            file_size = os.path.getsize(final_filepath) / (1024 * 1024)
            resolution = get_video_resolution(final_filepath)
            print(f"\n{Fore.GREEN}Download complete.{Style.RESET_ALL}\n")
            print(f"  - URL: {url}")
            print(f"  - File: {final_filepath}")
            print(f"  - Size: {file_size:.2f} MB")
            if resolution:
                print(f"  - Resolution: {resolution}px")
            return final_filepath
        
        # This part will now only be reached if the download fails
        print(f"\n{Fore.RED}Download failed after all attempts.{Style.RESET_ALL}")
        return None

    except Exception as e:
        print(f"\n{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
        return None