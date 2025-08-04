import os
import argparse
import sys
from colorama import Fore, Back, Style, init, deinit

# Add the 'modules' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'modules')))

from module_ffmpeg import download_ffmpeg
from module_ytdlp import download_video
from module_processor import process_video


def main():
    init()

    parser = argparse.ArgumentParser(description="Process a video file to separate audio stems or download a video.")
    parser.add_argument("--temp", action="store_true", help="If used, We will display paths, but we will not delete temporary files or dirs")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser for the 'process' command
    process_parser = subparsers.add_parser("separate", help="Process a video file to separate audio stems.")
    group = process_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to the input video file.")
    group.add_argument("--folder", help="Path to the folder containing video files.")

    # Subparser for the 'download' command
    download_parser = subparsers.add_parser("download", help="Download a video from a URL.")
    download_parser.add_argument("url", help="URL of the video to download.")
    download_parser.add_argument("filename", nargs='?', default=None, help="Optional: Filename for the downloaded video.")

    args = parser.parse_args()

    if args.command == "download":
        try:
            downloaded_file_path = download_video(args.url, args.filename)
            if downloaded_file_path:
                print(f"\n{Fore.GREEN}Script finished successfully.{Style.RESET_ALL}")
                print(f"Video downloaded to: {downloaded_file_path}")
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
                success = process_video(args.file, args.temp)
                if success:
                    print(f"\n{Fore.GREEN}Script finished successfully for {args.file}.{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.RED}Script failed for {args.file}. Check logs above.{Style.RESET_ALL}")
            elif args.folder:
                video_files = [f for f in os.listdir(args.folder) if f.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.flv'))]
                if not video_files:
                    print(f"{Fore.YELLOW}No video files found in the specified folder: {args.folder}{Style.RESET_ALL}")
                    return

                for video_file in video_files:
                    file_path = os.path.join(args.folder, video_file)
                    print(f"\n{Back.BLUE}{Fore.WHITE}--- Starting processing for: {file_path} ---{Style.RESET_ALL}")
                    success = process_video(file_path, args.temp)
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