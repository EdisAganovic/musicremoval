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
        # Use UV to upgrade yt-dlp.
        update_cmd = ["uv", "pip", "install", "--upgrade", "yt-dlp"]
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

def download_video(url, filename=None, cookies_file=None):
    """
    Downloads a video from a URL using yt-dlp into a 'download' folder.
    Returns the path to the downloaded file.
    """
    if not check_and_update_ytdlp():
        return None

    download_folder = "download"
    os.makedirs(download_folder, exist_ok=True)

    try:
        # 1. Get the final filename from yt-dlp before downloading
        output_template = os.path.join(download_folder, filename if filename else "%(title)s.%(ext)s")
        get_filename_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--get-filename",
            "--ignore-errors",
            "--fragment-retries", "infinite",
            "--retry-sleep", "fragment:exp=1:300",
            "--extractor-args", "youtube:player_client=default,ios",
            "-o", output_template,
        ]
        if cookies_file and os.path.exists(cookies_file):
            print(f"{Fore.CYAN}Using cookies from: {cookies_file}{Style.RESET_ALL}")
            get_filename_cmd.extend(["--cookies", cookies_file])
        get_filename_cmd.append(url)

        simple_filename_cmd = [
           "yt_dlp",
            "--get-filename",
            "-o", output_template,
            url
        ]

        print(f"{Fore.MAGENTA}Determining filename...{Style.RESET_ALL}")
        # Remove check=True to handle yt-dlp errors manually
        result = subprocess.run(get_filename_cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            print(f"\n{Fore.RED}An error occurred while trying to get video metadata (Exit Code: {result.returncode}).{Style.RESET_ALL}")
            if result.stderr:
                print(f"{Fore.RED}{result.stderr.strip()}{Style.RESET_ALL}")

            # --- List available formats on metadata error ---
            print(f"\n{Fore.CYAN}--- Listing available formats for {url} ---")
            list_formats_cmd = [
                sys.executable, "-m", "yt_dlp", "-F", url
            ]
            if cookies_file and os.path.exists(cookies_file):
                list_formats_cmd.extend(["--cookies", cookies_file])
            
            list_result = subprocess.run(list_formats_cmd, capture_output=True, text=True, encoding='utf-8')
            if list_result.stdout:
                print(list_result.stdout)
            if list_result.stderr:
                print(f"{Fore.RED}{list_result.stderr.strip()}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}--- End of available formats ---")
            return None

        final_filepath = result.stdout.strip().splitlines()[-1]

        # 2. Check if the file already exists
        if os.path.exists(final_filepath):
            print(f"{Fore.YELLOW}Video '{final_filepath}' already exists. Skipping download.{Style.RESET_ALL}")
            return final_filepath

        # 3. If it doesn't exist, download it
        print(f"{Fore.CYAN}Downloading to '{final_filepath}'...{Style.RESET_ALL}")
        
        # --- First Attempt: High-quality format ---
        print(f"{Fore.CYAN}Attempt 1: Trying high-quality format...{Style.RESET_ALL}")
        download_cmd_hq = [
            sys.executable, "-m", "yt_dlp",
            "--ignore-errors",
            "--fragment-retries", "infinite",
            "--retry-sleep", "fragment:exp=1:300",
            #"--extractor-args", "youtube:player_client=default,ios",
            "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
            "-o", output_template,
            "--progress",
        ]
        if cookies_file and os.path.exists(cookies_file):
            download_cmd_hq.extend(["--cookies", cookies_file])
        download_cmd_hq.append(url)
        
        process = subprocess.run(download_cmd_hq, capture_output=True, text=True, encoding='utf-8')

        # --- Check for success, if not, try fallback ---
        if not (os.path.exists(final_filepath) and os.path.getsize(final_filepath) > 0):
            print(f"\n{Fore.YELLOW}High-quality format failed. Trying fallback format...{Style.RESET_ALL}")
            if process.stderr:
                 print(f"{Fore.YELLOW}Details from previous attempt: {process.stderr.strip()}{Style.RESET_ALL}")

            # --- Second Attempt: Fallback format ---
            download_cmd_fallback = [
                sys.executable, "-m", "yt_dlp",
                "--ignore-errors",
                "--fragment-retries", "infinite",
                "--retry-sleep", "fragment:exp=1:300",
                "--extractor-args", "youtube:player_client=default,ios",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "-o", output_template,
                "--progress",
            ]
            if cookies_file and os.path.exists(cookies_file):
                download_cmd_fallback.extend(["--cookies", cookies_file])
            download_cmd_fallback.append(url)

            process = subprocess.run(download_cmd_fallback, capture_output=True, text=True, encoding='utf-8')

        # 4. Verify final download and print stats
        if os.path.exists(final_filepath) and os.path.getsize(final_filepath) > 0:
            if process.returncode != 0:
                print(f"\n{Fore.YELLOW}Warning: yt-dlp finished with exit code {process.returncode}, but the file was downloaded. Proceeding...{Style.RESET_ALL}")

            file_size = os.path.getsize(final_filepath) / (1024 * 1024)
            resolution = get_video_resolution(final_filepath)
            print(f"\n{Fore.GREEN}Download complete.{Style.RESET_ALL}\n")
            print(f"  - URL: {url}")
            print(f"  - File: {final_filepath}")
            print(f"  - Size: {file_size:.2f} MB")
            if resolution:
                print(f"  - Resolution: {resolution}px")
            return final_filepath
        else:
            # This is a definite failure, so we'll list the available formats for debugging.
            print(f"\n{Fore.RED}Download failed. File '{final_filepath}' not found or is empty after all attempts.{Style.RESET_ALL}")
            if process.stderr:
                print(f"{Fore.RED}Error details from last attempt (Exit Code: {process.returncode}):{Style.RESET_ALL}")
                print(f"{Fore.RED}{process.stderr.strip()}{Style.RESET_ALL}")
            
            print(f"\n{Fore.CYAN}--- Listing available formats for {url} ---{Style.RESET_ALL}")
            list_formats_cmd = [
                sys.executable, "-m", "yt_dlp", "-F", url
            ]
            if cookies_file and os.path.exists(cookies_file):
                list_formats_cmd.extend(["--cookies", cookies_file])
            
            list_result = subprocess.run(list_formats_cmd, capture_output=True, text=True, encoding='utf-8')
            if list_result.stdout:
                print(list_result.stdout)
            if list_result.stderr:
                print(f"{Fore.RED}{list_result.stderr.strip()}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}--- End of available formats ---")
            return None

    except subprocess.CalledProcessError as e:
        # This will now only catch errors from the get_filename_cmd
        print(f"\n{Fore.RED}An error occurred while trying to get video metadata (Exit Code: {e.returncode}).{Style.RESET_ALL}")
        print(f"{Fore.RED}{e.stderr}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"\n{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
        return None



