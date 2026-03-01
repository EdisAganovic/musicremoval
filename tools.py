"""
UTILITY CLI - Inspect audio tracks in video files.

STANDALONE: Can run independently via `python tools.py list_tracks <file>`

USAGE:
  python tools.py list_tracks <video_file>  → List all audio tracks with language

DEPENDENCIES:
  - module_ffmpeg.get_audio_tracks(): Uses FFprobe to extract track info
  - module_ffmpeg.download_ffmpeg(): Auto-downloads FFmpeg if missing

OUTPUT:
  Prints track index and language for each audio stream
"""
import argparse
import sys
import os
from colorama import Fore, Style

# Add the 'modules' directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'modules')))

try:
    from module_ffmpeg import get_audio_tracks, download_ffmpeg
except ImportError as e:
    print(f"{Fore.RED}Error: Failed to import required modules.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Please ensure that 'modules/module_ffmpeg.py' and its dependencies are accessible.{Style.RESET_ALL}")
    print(f"Details: {e}")
    sys.exit(1)

def main():
    """
    Main function to parse arguments and display audio tracks from a video file.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="A utility script to inspect video files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Add command for listing audio tracks
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    parser_list_tracks = subparsers.add_parser('list_tracks', help='List all audio tracks from a video file.')
    parser_list_tracks.add_argument('input_file', type=str, help='The path to the video file.')

    # Parse command-line arguments
    args = parser.parse_args()

    # Execute the appropriate command
    if args.command == 'list_tracks':
        # Ensure ffmpeg is available before proceeding
        if not download_ffmpeg():
            print(f"{Fore.RED}FFmpeg is not available. Cannot proceed.{Style.RESET_ALL}")
            sys.exit(1)
            
        video_path = args.input_file
        
        # Verify the video file exists
        if not os.path.exists(video_path):
            print(f"{Fore.RED}Error: The file '{video_path}' does not exist.{Style.RESET_ALL}")
            sys.exit(1)
            
        # Retrieve and display the audio tracks
        print(f"\n{Style.BRIGHT}Reading audio tracks from: {video_path}{Style.RESET_ALL}")
        audio_tracks = get_audio_tracks(video_path)
        
        if not audio_tracks:
            print(f"{Fore.YELLOW}No audio tracks were found in the file.{Style.RESET_ALL}")
        else:
            print(f"\n{Style.BRIGHT}{Fore.GREEN}Available Audio Tracks:{Style.RESET_ALL}")
            for track in audio_tracks:
                print(f"  - Index: {track['index']}, Language: {track['language']}")
            print(f"\n{Fore.CYAN}Found {len(audio_tracks)} audio track(s).{Style.RESET_ALL}")

    else:
        # If no command is specified, print the help message
        parser.print_help()

if __name__ == "__main__":
    main()
