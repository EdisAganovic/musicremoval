"""
MAIN ENTRY POINT - CLI for vocal separation workflow.

WORKFLOW:
  1. download → module_ytdlp.download_video() → saves to ./downloads/
  2. separate → module_processor.process_file() → orchestrates Demucs/Spleeter
  3. output → saved to ./nomusic/ with metadata in video.json

COMMANDS:
  - download <url> [filename] [--separate]  → Download from YouTube
  - separate --file|--folder [--duration]   → Separate vocals from file/folder

KEY FILES:
  - video.json: Library database + quality presets
  - download_queue.json: Queue state
  - notifications.json: Alert history

MODULES USED:
  - module_ffmpeg: FFmpeg management (auto-downloads if missing)
  - module_ytdlp: YouTube downloading via yt-dlp
  - module_processor: Main separation orchestrator (Demucs + Spleeter)
"""
import os
import argparse
import sys
from colorama import Fore, Back, Style, init, deinit

# Add the 'modules' directory to the Python path to allow direct imports of module_* files
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'modules')))

from module_ffmpeg import download_ffmpeg
from module_ytdlp import download_video
from module_processor import process_file, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS


def main():
    """
    Parses command line arguments and dispatches to the appropriate module (download or separate).
    Handles colorama initialization and cleanup.
    """
    init()

    parser = argparse.ArgumentParser(description="Process a video or audio file to separate vocals using Demucs and Spleeter.")
    parser.add_argument("--temp", action="store_true", help="If used, We will display paths, but we will not delete temporary files or dirs")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser for the 'process' command
    process_parser = subparsers.add_parser("separate", help="Process a video or audio file to separate vocals.")
    group = process_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to the input video or audio file.")
    group.add_argument("--folder", help="Path to the folder containing video/audio files.")
    process_parser.add_argument("--duration", type=int, help="Limit processing to the first N seconds (e.g., 120 for 2 minutes).")

    # Subparser for the 'download' command
    download_parser = subparsers.add_parser("download", help="Download a video from a URL.")
    download_parser.add_argument("url", help="URL of the video to download.")
    download_parser.add_argument("filename", nargs='?', default=None, help="Optional: Filename for the downloaded video.")
    download_parser.add_argument("--separate", action="store_true", help="If used, automatically separate vocals after downloading.")

    args = parser.parse_args()

    if args.command == "download":
        try:
            downloaded_file_path = download_video(args.url, args.filename)
            if downloaded_file_path:
                print(f"\n{Fore.GREEN}Script finished successfully.{Style.RESET_ALL}")
                print(f"Video downloaded to: {downloaded_file_path}")
                
                # Auto-separate if flag is set
                if args.separate:
                    print(f"\n{Fore.CYAN}Starting vocal separation...{Style.RESET_ALL}")
                    if not download_ffmpeg():
                        print(f"\n{Fore.RED}FFmpeg download failed. Cannot proceed with separation.{Style.RESET_ALL}")
                    else:
                        success = process_file(downloaded_file_path, args.temp)
                        if success:
                            print(f"\n{Fore.GREEN}Vocal separation completed successfully.{Style.RESET_ALL}")
                        else:
                            print(f"\n{Fore.RED}Vocal separation failed. Check logs above.{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.RED}Script failed. Check logs above.{Style.RESET_ALL}")
        finally:
            deinit()
    elif args.command == "separate":
        if not download_ffmpeg():
            print(f"\n{Fore.RED}FFmpeg download failed. Cannot proceed with video processing.{Style.RESET_ALL}")
            deinit()
            return

        try:
            if args.file:
                success = process_file(args.file, args.temp, args.duration)
                if success:
                    print(f"\n{Fore.GREEN}Script finished successfully for {args.file}.{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.RED}Script failed for {args.file}. Check logs above.{Style.RESET_ALL}")
            elif args.folder:
                # Combine video and audio extensions for batch processing
                supported_extensions = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS
                media_files = [f for f in os.listdir(args.folder) if f.lower().endswith(supported_extensions)]
                
                if not media_files:
                    print(f"{Fore.YELLOW}No video or audio files found in the specified folder: {args.folder}{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Supported formats: {', '.join(supported_extensions)}{Style.RESET_ALL}")
                    return

                print(f"{Fore.CYAN}Found {len(media_files)} files to process.{Style.RESET_ALL}")
                
                for media_file in media_files:
                    file_path = os.path.join(args.folder, media_file)
                    print(f"\n{Back.BLUE}{Fore.WHITE}--- Starting processing for: {file_path} ---{Style.RESET_ALL}")
                    success = process_file(file_path, args.temp, args.duration)
                    if success:
                        print(f"\n{Fore.GREEN}--- Finished processing successfully for: {file_path} ---{Style.RESET_ALL}")
                    else:
                        print(f"\n{Fore.RED}--- Finished processing with errors for: {file_path} ---{Style.RESET_ALL}")

        finally:
            deinit()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()