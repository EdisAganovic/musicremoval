import subprocess
import sys
import os
from colorama import Fore, Style
from module_ffmpeg import get_video_resolution

def check_and_update_ytdlp():
    """
    Checks for yt-dlp updates and installs or upgrades it.
    """
    print(f"{Fore.CYAN}Checking for yt-dlp updates...{Style.RESET_ALL}")
    try:
        # Use pip to upgrade yt-dlp. This will install it if it's not present.
        update_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        print(f"{Fore.MAGENTA}Executing: {' '.join(update_cmd)}{Style.RESET_ALL}")
        result = subprocess.run(update_cmd, check=True, capture_output=True, text=True)
        if "Requirement already satisfied" in result.stdout:
            print(f"{Fore.GREEN}yt-dlp is up to date.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}yt-dlp has been installed/updated successfully.{Style.RESET_ALL}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error updating yt-dlp: {e}\n{e.stderr}{Style.RESET_ALL}")
        return False

def download_video(url, filename=None):
    """
    Downloads a video from a URL using yt-dlp into a 'download' folder.
    Returns the path to the downloaded file.
    """
    if not check_and_update_ytdlp():
        return None

    download_folder = "download"
    os.makedirs(download_folder, exist_ok=True)

    print(f"\n{Fore.CYAN}Starting video download from URL: {url}{Style.RESET_ALL}")

    try:
        # 1. Get the final filename from yt-dlp before downloading
        output_template = os.path.join(download_folder, filename if filename else "%(title)s.%(ext)s")
        get_filename_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--get-filename",
            "-o", output_template,
            url
        ]
        
        print(f"{Fore.MAGENTA}Determining filename...{Style.RESET_ALL}")
        result = subprocess.run(get_filename_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        final_filepath = result.stdout.strip().splitlines()[-1]

        # 2. Check if the file already exists
        if os.path.exists(final_filepath):
            print(f"{Fore.YELLOW}Video '{final_filepath}' already exists. Skipping download.{Style.RESET_ALL}")
            return final_filepath

        # 3. If it doesn't exist, download it
        print(f"{Fore.CYAN}Downloading to '{final_filepath}'...{Style.RESET_ALL}")
        download_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extractor-args", "youtube:player_client=default,ios",
            "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
            "-o", output_template,
            "--no-progress", # Quieter output
            url
        ]
        
        # Using run instead of Popen for simpler blocking execution
        process = subprocess.run(download_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        
        # Output stdout/stderr for debugging if needed
        # print(process.stdout)
        # if process.stderr:
        #     print(process.stderr)

        # 4. Verify download and print stats
        if os.path.exists(final_filepath):
            file_size = os.path.getsize(final_filepath) / (1024 * 1024)  # in MB
            resolution = get_video_resolution(final_filepath)
            print(f"\n{Fore.GREEN}Download complete.{Style.RESET_ALL}")
            print(f"  - File: {final_filepath}")
            print(f"  - Size: {file_size:.2f} MB")
            if resolution:
                print(f"  - Resolution: {resolution}")
            return final_filepath
        else:
            print(f"\n{Fore.RED}Download failed. File '{final_filepath}' not found after download process.{Style.RESET_ALL}")
            return None

    except subprocess.CalledProcessError as e:
        print(f"\n{Fore.RED}An error occurred with yt-dlp (Exit Code: {e.returncode}).{Style.RESET_ALL}")
        # Print stderr for more detailed error info
        print(f"{Fore.RED}{e.stderr}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"\n{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
        return None



