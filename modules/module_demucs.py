import os
import subprocess
import tempfile
import shutil
from colorama import Fore, Style
from module_ffmpeg import get_audio_duration

def separate_with_demucs(temp_audio_wav_path, demucs_base_out_path, base_audio_name_no_ext):
    """
    Separates audio using Demucs, handling segmentation for long files.
    """
    print(f"\n{Fore.CYAN}3. Separating with Demucs (htdemucs model) into: {demucs_base_out_path}...{Style.RESET_ALL}")
    demucs_vocal_wav_path = None
    temp_demucs_segments_dir = None
    try:
        os.makedirs(demucs_base_out_path, exist_ok=True)

        audio_duration = get_audio_duration(temp_audio_wav_path)
        if audio_duration is None:
            print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Demucs separation.{Style.RESET_ALL}")
            return None, None

        DEMUCS_SEGMENT_DURATION_SECONDS = 600  # 10 minutes

        if audio_duration > DEMUCS_SEGMENT_DURATION_SECONDS:
            print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds 10 minutes. Splitting audio for Demucs...{Style.RESET_ALL}\n")
            temp_demucs_segments_dir = tempfile.mkdtemp()
            demucs_segment_vocal_paths = []
            split_audio_paths = []

            current_start_time = 0
            segment_index = 0

            while current_start_time < audio_duration:
                segment_duration = min(DEMUCS_SEGMENT_DURATION_SECONDS, audio_duration - current_start_time)
                segment_filename = f"part_{segment_index:03d}.wav"
                segment_output_path = os.path.join(temp_demucs_segments_dir, segment_filename)

                ffmpeg_split_cmd = [
                    "ffmpeg", "-y", 
                    "-loglevel", "error",
                    "-i", temp_audio_wav_path,
                    "-ss", str(current_start_time),
                    "-t", str(segment_duration),
                    segment_output_path
                ]
                print(f"- Splitting audio: {segment_filename} from {current_start_time:.2f}s for {segment_duration:.2f}s...")
                subprocess.run(ffmpeg_split_cmd, check=True)
                split_audio_paths.append(segment_output_path)

                current_start_time += segment_duration
                segment_index += 1

            print(f"\n{Fore.GREEN}\N{check mark} Audio splitted into {len(split_audio_paths)} segments for Demucs.{Style.RESET_ALL}")

            for i, segment_path in enumerate(split_audio_paths):
                segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                
                demucs_cmd = ["demucs", "-n", "htdemucs", "-o", demucs_base_out_path, segment_path]
                print(f"\n{Fore.MAGENTA}Processing segment {i+1}/{len(split_audio_paths)} with Demucs: \n{' '.join(demucs_cmd)}{Style.RESET_ALL}")
                subprocess.run(demucs_cmd, check=True)

                segment_vocal_path = os.path.join(demucs_base_out_path, "htdemucs", segment_base_name, "vocals.wav")
                if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                    demucs_segment_vocal_paths.append(segment_vocal_path)
                else:
                    print(f"{Fore.YELLOW}Warning: Demucs vocals for segment {segment_base_name} not found or empty at {segment_vocal_path}. Skipping this segment.{Style.RESET_ALL}")

            if not demucs_segment_vocal_paths:
                print(f"{Fore.RED}Error: No Demucs vocal segments were successfully generated. Demucs output will not be used for combination.{Style.RESET_ALL}")
                return None, temp_demucs_segments_dir
            else:
                concat_list_path = os.path.join(temp_demucs_segments_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for p in demucs_segment_vocal_paths:
                        f.write(f"file '{os.path.abspath(p)}'\n")

                final_demucs_vocals_filename = "concatenated_demucs_vocals.wav"
                final_demucs_vocals_temp_path = os.path.join(temp_demucs_segments_dir, final_demucs_vocals_filename)
                
                ffmpeg_concat_cmd = [
                    "ffmpeg", "-y", 
                    "-loglevel", "error",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    final_demucs_vocals_temp_path
                ]
                print(f"\nJoining Demucs vocal segments to: {final_demucs_vocals_temp_path}")
                subprocess.run(ffmpeg_concat_cmd, check=True)
                demucs_vocal_wav_path = final_demucs_vocals_temp_path
                print(f"\n{Fore.GREEN}\N{check mark} All Demucs vocal segments joined successfully.{Style.RESET_ALL}")
        else:
            demucs_cmd = [
                "demucs",
                "--no-progress",
                "-n", "htdemucs",
                "-o", demucs_base_out_path,
                temp_audio_wav_path
            ]
            print(f"{Fore.MAGENTA}Executing: {' '.join(demucs_cmd)}\n{Style.RESET_ALL}")
            subprocess.run(demucs_cmd, check=True)
            demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")
            print(f"\n{Fore.GREEN}\N{check mark} Demucs separation complete. Output in: {demucs_base_out_path}\n{Style.RESET_ALL}")

        if not os.path.exists(demucs_vocal_wav_path) or os.path.getsize(demucs_vocal_wav_path) == 0:
            print(f"{Fore.YELLOW}Warning: Demucs vocals not found or empty at {demucs_vocal_wav_path}.{Style.RESET_ALL}")
            return None, temp_demucs_segments_dir

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error with demucs separation: {e}{Style.RESET_ALL}")
        return None, temp_demucs_segments_dir
    
    return demucs_vocal_wav_path, temp_demucs_segments_dir