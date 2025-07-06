import os
import subprocess
import tempfile
import shutil
import argparse
from colorama import Fore, Back, Style, init, deinit
from concurrent.futures import ThreadPoolExecutor, as_completed

from module_cuda import check_gpu_cuda_support
from module_ffmpeg import get_audio_duration
from module_spleeter import separate_with_spleeter
from module_demucs import separate_with_demucs
from module_file import download_file_concurrent
from module_audio import align_audio_tracks
from module_ytdlp import download_video

def _check_program_installed(program_name):
    """Provjera dodatnih alata """
    if shutil.which(program_name):
        print(f"{Fore.GREEN}'{program_name}' instaliran.{Style.RESET_ALL}")
        return True
    else:
        print(f"{Fore.RED}Error: '{program_name}' not found in system PATH.{Style.RESET_ALL}")
        print(f"{Fore.RED}Please ensure '{program_name}' is installed and its executable directory is added to your system's PATH environment variable.{Style.RESET_ALL}")
        return False

def process_video(input_file):
    if not os.path.exists(input_file):
        print(f"{Fore.RED}Error: Input video file '{input_file}' not found.{Style.RESET_ALL}")
        return False
    
    original_duration = get_audio_duration(input_file)
    if original_duration is None:
        print(f"{Fore.YELLOW}Warning: Could not determine audio duration for the original video.{Style.RESET_ALL}")

    print(f"\n{Back.MAGENTA}{Fore.WHITE}# SISTEMSKA PROVJERA {Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}1. Provjera dodatnih alata da li su instalirani{Style.RESET_ALL}")
    if not _check_program_installed("ffmpeg"):
        return False
    if not _check_program_installed("spleeter"):
        return False
    if not _check_program_installed("demucs"):
        return False

    cuda_is_available = check_gpu_cuda_support()

    if not cuda_is_available:
        print(f"{Fore.RED}GPU akceleracija nije podržana.{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}GPU akceleracija podržana.{Style.RESET_ALL}")

    temp_audio_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_audio_wav_path = temp_audio_wav_file.name
    temp_audio_wav_file.close()

    base_audio_name_no_ext = os.path.splitext(os.path.basename(temp_audio_wav_path))[0]

    spleeter_out_path = "spleeter_out"
    demucs_base_out_path = "demucs_out"

    temp_combined_vocals_aac_file = tempfile.NamedTemporaryFile(suffix=".aac", delete=False)
    combined_vocals_aac_path = temp_combined_vocals_aac_file.name
    temp_combined_vocals_aac_file.close()

    temp_aligned_spleeter_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_spleeter.wav", delete=False)
    aligned_spleeter_vocals_path = temp_aligned_spleeter_vocals.name
    temp_aligned_spleeter_vocals.close()

    temp_aligned_demucs_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_demucs.wav", delete=False)
    aligned_demucs_vocals_path = temp_aligned_demucs_vocals.name
    temp_aligned_demucs_vocals.close()

    temp_spleeter_segments_dir = None
    spleeter_vocal_wav_path = None

    try:
        print(f"\n{Back.YELLOW}{Fore.BLACK}# UKLANJANJE MUZIKE ZAPOČETO ZA FAJL: {input_file} ---{Style.RESET_ALL}\n")

        print(f"{Fore.CYAN}1. Extracting audio to temporary WAV: {temp_audio_wav_path}...{Style.RESET_ALL}")
        ffmpeg_cmd = ["ffmpeg", "-y","-loglevel","error", "-i", input_file, temp_audio_wav_path]
        print(f"{Fore.MAGENTA}Executing: {' '.join(ffmpeg_cmd)}\n")
        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"{Fore.GREEN}Audio extraction complete.\n{Style.RESET_ALL}")
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error extracting audio: {e}{Style.RESET_ALL}")
            return False

        spleeter_vocal_wav_path, temp_spleeter_segments_dir = separate_with_spleeter(temp_audio_wav_path, spleeter_out_path, base_audio_name_no_ext)
        demucs_vocal_wav_path, temp_demucs_segments_dir = separate_with_demucs(temp_audio_wav_path, demucs_base_out_path, base_audio_name_no_ext)

        print(f"{Fore.CYAN}4. Aligning and combining Spleeter (WAV) and Demucs (WAV) vocals into temporary AAC: {combined_vocals_aac_path}...{Style.RESET_ALL}")

        spleeter_input_exists = spleeter_vocal_wav_path and os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0
        demucs_input_exists = demucs_vocal_wav_path and os.path.exists(demucs_vocal_wav_path) and os.path.getsize(demucs_vocal_wav_path) > 0

        if not spleeter_input_exists and not demucs_input_exists:
            print(f"{Fore.RED}Error: Neither Spleeter nor Demucs vocal files were successfully generated. Cannot combine.{Style.RESET_ALL}")
            return False
        elif not spleeter_input_exists:
            print(f"{Fore.YELLOW}Only Demucs vocals found. Using Demucs vocals directly for the combined track.{Style.RESET_ALL}")
            try:
                combine_cmd = ["ffmpeg", "-y", "-i", demucs_vocal_wav_path, "-c:a", "libfdk_aac", "-b:a", "192k", combined_vocals_aac_path]
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}")
                subprocess.run(combine_cmd, check=True)
                print(f"{Fore.GREEN}Demucs vocals re-encoded to AAC successfully.{Style.RESET_ALL}")
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}Error re-encoding Demucs vocals: {e}{Style.RESET_ALL}")
                return False
        elif not demucs_input_exists:
            print(f"{Fore.YELLOW}Only Spleeter vocals found. Using Spleeter vocals directly for the combined track.{Style.RESET_ALL}")
            try:
                combine_cmd = ["ffmpeg", "-y", "-i", spleeter_vocal_wav_path, "-c:a", "libfdk_aac", "-b:a", "192k", combined_vocals_aac_path]
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}")
                subprocess.run(combine_cmd, check=True)
                print(f"{Fore.GREEN}\N{check mark} Spleeter vocals re-encoded to AAC successfully.{Style.RESET_ALL}")
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}\N{CROSS MARK}' Error re-encoding Spleeter vocals: {e}{Style.RESET_ALL}")
                return False
        else:
            aligned_spleeter, aligned_demucs = align_audio_tracks(spleeter_vocal_wav_path, demucs_vocal_wav_path, aligned_spleeter_vocals_path, aligned_demucs_vocals_path)

            if aligned_spleeter and aligned_demucs:
                try:
                    combine_cmd = [
                        "ffmpeg",
                        "-loglevel", "error",
                        "-y",
                        "-i", aligned_spleeter,
                        "-i", aligned_demucs,
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[a]",
                        "-map", "[a]",
                        "-c:a", "libfdk_aac",
                        "-b:a", "192k",
                        combined_vocals_aac_path
                    ]
                    print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}")
                    subprocess.run(combine_cmd, check=True)
                    print(f"\n{Fore.GREEN}\N{check mark} Vocals combined successfully.{Style.RESET_ALL}")
                except subprocess.CalledProcessError as e:
                    print(f"{Fore.RED}\N{CROSS MARK}' Error combining AAC files: {e}{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}Error: Alignment failed. Cannot combine vocal tracks.{Style.RESET_ALL}")
                return False

        output_video = f"nomusic-{os.path.basename(input_file)}"
        
        print(f"\n{Fore.CYAN}5. Creating final video: {output_video}...{Style.RESET_ALL}")
        try:
            final_ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-y",
                "-i", input_file,
                "-i", combined_vocals_aac_path,
                "-c:v", "copy",
                "-c:a", "libfdk_aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_video
            ]
            print(f"\n{Fore.MAGENTA}Executing: {' '.join(final_ffmpeg_cmd)}")
            subprocess.run(final_ffmpeg_cmd, check=True)
            print(f"\n{Fore.GREEN}\N{check mark} Successfully created {output_video}{Style.RESET_ALL}")

            # Get final audio duration and compare
            final_duration = get_audio_duration(output_video)
            if final_duration is not None and original_duration is not None:
                duration_diff = abs(original_duration - final_duration)
                print(f"{Fore.BLUE}Final video audio duration: {final_duration:.2f} seconds{Style.RESET_ALL}")
                if duration_diff > 1: # Allow for a small tolerance
                    print(f"{Fore.YELLOW}Warning: Duration difference of {duration_diff:.2f} seconds between original and final video.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.GREEN}Audio duration is consistent.{Style.RESET_ALL}")

            return True
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}\N{cross mark}Error creating new video: {e}{Style.RESET_ALL}")
            return False

    finally:
        print(f"\n{Fore.CYAN}--- Cleanup of temporary files ---{Style.RESET_ALL}")
        for f_path in [temp_audio_wav_path, combined_vocals_aac_path, 
                       aligned_spleeter_vocals_path, aligned_demucs_vocals_path]:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    print(f"{Fore.BLUE}Removed temporary file: {f_path}{Style.RESET_ALL}")
                except OSError as e:
                    print(f"{Fore.RED}Error removing temporary file {f_path}: {e}{Style.RESET_ALL}")

        if temp_spleeter_segments_dir and os.path.exists(temp_spleeter_segments_dir):
            try:
                shutil.rmtree(temp_spleeter_segments_dir)
                print(f"{Fore.BLUE}Removed temporary directory: {temp_spleeter_segments_dir}{Style.RESET_ALL}")
            except OSError as e:
                print(f"{Fore.RED}Error removing temporary directory {temp_spleeter_segments_dir}: {e}{Style.RESET_ALL}")

        if temp_demucs_segments_dir and os.path.exists(temp_demucs_segments_dir):
            try:
                shutil.rmtree(temp_demucs_segments_dir)
                print(f"{Fore.BLUE}Removed temporary directory: {temp_demucs_segments_dir}{Style.RESET_ALL}")
            except OSError as e:
                print(f"{Fore.RED}Error removing temporary directory {temp_demucs_segments_dir}: {e}{Style.RESET_ALL}")

        for dir_path in [spleeter_out_path, demucs_base_out_path]:
            if os.path.exists(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    print(f"{Fore.BLUE}Removed output directory: {dir_path}{Style.RESET_ALL}")
                except OSError as e:
                    print(f"{Fore.RED}Error removing output directory {dir_path}: {e}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}--- Processing complete ---{Style.RESET_ALL}")


if __name__ == "__main__":
    init()

    parser = argparse.ArgumentParser(description="Process a video file to separate audio stems or download a video.")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser for the 'process' command
    process_parser = subparsers.add_parser("separate", help="Process a video file to separate audio stems.")
    process_parser.add_argument("input_file", help="Path to the input video file.")

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
    elif args.command == "process":
        files_config = [
            {"url": "https://oblak.pronameserver.xyz/public.php/dav/files/8mW9BJCqLXX5ecp/?accept=zip", "filename": "ffmpeg.exe"},
            {"url": "https://oblak.pronameserver.xyz/public.php/dav/files/mGjWEPpJgC7xfiz/?accept=zip", "filename": "ffprobe.exe"}
        ]

        print(f"\n{Back.RED}{Fore.WHITE}# FFMPEG Download {Style.RESET_ALL}\n")
        files_to_actually_download = []
        for file_info in files_config:
            filename = file_info["filename"]
            if os.path.exists(filename):
                print(f"- Skipping '{filename}': File already exists locally.")
            else:
                files_to_actually_download.append(file_info)
                print(f"- '{filename}' does not exist locally, will attempt to download.")

        if not files_to_actually_download:
            print("\nNo new files to download. All specified files already exist locally.")
        else:
            print("\n--- Starting Concurrent Downloads ---")
            with ThreadPoolExecutor(max_workers=len(files_to_actually_download)) as executor:
                future_to_file = {executor.submit(download_file_concurrent, f["url"], f["filename"]): f for f in files_to_actually_download}

                for future in as_completed(future_to_file):
                    original_file_info = future_to_file[future]
                    success, filename = future.result()

                    if success:
                        print(f"[{filename}] Download finished.")
                    else:
                        print(f"[{filename}] Download failed.")

        try:
            success = process_video(args.input_file)
            if success:
                print(f"\n{Fore.GREEN}Script finished successfully for {args.input_file}.{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.RED}Script failed for {args.input_file}. Check logs above.{Style.RESET_ALL}")
        finally:
            deinit()
    else:
        parser.print_help()

