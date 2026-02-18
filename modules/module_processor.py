"""
Core processing module that orchestrates the vocal extraction pipeline.
It handles video/audio input, track selection, model execution, alignment, and final output creation.
"""
import json
import os
import subprocess
import tempfile
import shutil
from colorama import Fore, Back, Style

from module_cuda import check_gpu_cuda_support
from module_ffmpeg import get_audio_duration, FFMPEG_EXE, convert_audio_with_ffmpeg, get_audio_tracks
from module_spleeter import separate_with_spleeter
from module_demucs import separate_with_demucs
from module_audio import align_audio_tracks, mix_audio_tracks, calculate_audio_lag

# Supported file extensions
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.wmv')
AUDIO_EXTENSIONS = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma')

# Local temp directory
TEMP_DIR = "_temp"

# Default configuration
DEFAULT_CONFIG = {
    "video": {
        "codec": "copy",
        "bitrate": None
    },
    "audio": {
        "codec": "aac",
        "bitrate": "192k"
    },
    "output": {
        "format": "mp4"
    }
}

def load_config(config_path='video.json'):
    """
    Loads and validates the video.json configuration file.
    Returns a validated config dict, falling back to defaults on any error.
    """
    config = DEFAULT_CONFIG.copy()
    
    if not os.path.exists(config_path):
        print(f"{Fore.YELLOW}Config file '{config_path}' not found. Using default settings.{Style.RESET_ALL}")
        return config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        
        # Validate and merge user config with defaults
        if not isinstance(user_config, dict):
            raise ValueError("Config must be a JSON object")
        
        # Validate video settings
        if 'video' in user_config:
            if not isinstance(user_config['video'], dict):
                raise ValueError("'video' must be an object")
            video_config = user_config['video']
            if 'codec' in video_config:
                if not isinstance(video_config['codec'], str):
                    raise ValueError("'video.codec' must be a string")
                config['video']['codec'] = video_config['codec']
            if 'bitrate' in video_config:
                if video_config['bitrate'] is not None and not isinstance(video_config['bitrate'], str):
                    raise ValueError("'video.bitrate' must be a string (e.g., '1800k') or null")
                config['video']['bitrate'] = video_config['bitrate']
        
        # Validate audio settings
        if 'audio' in user_config:
            if not isinstance(user_config['audio'], dict):
                raise ValueError("'audio' must be an object")
            audio_config = user_config['audio']
            if 'codec' in audio_config:
                if not isinstance(audio_config['codec'], str):
                    raise ValueError("'audio.codec' must be a string")
                config['audio']['codec'] = audio_config['codec']
            if 'bitrate' in audio_config:
                if audio_config['bitrate'] is not None and not isinstance(audio_config['bitrate'], str):
                    raise ValueError("'audio.bitrate' must be a string (e.g., '128k') or null")
                config['audio']['bitrate'] = audio_config['bitrate']
        
        # Validate output settings
        if 'output' in user_config:
            if not isinstance(user_config['output'], dict):
                raise ValueError("'output' must be an object")
            output_config = user_config['output']
            if 'format' in output_config:
                if not isinstance(output_config['format'], str):
                    raise ValueError("'output.format' must be a string")
                config['output']['format'] = output_config['format']
        
        # Validate processing settings
        if 'processing' in user_config:
            if not isinstance(user_config['processing'], dict):
                raise ValueError("'processing' must be an object")
            proc_config = user_config['processing']
            if 'demucs_workers' in proc_config:
                if not isinstance(proc_config['demucs_workers'], int):
                    raise ValueError("'processing.demucs_workers' must be an integer")
                config['processing'] = {'demucs_workers': proc_config['demucs_workers']}
        else:
            config['processing'] = {'demucs_workers': 2} # Default
        
        print(f"{Fore.GREEN}Configuration loaded successfully from '{config_path}'.{Style.RESET_ALL}")
        return config
        
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}Error: Invalid JSON in '{config_path}': {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Using default settings.{Style.RESET_ALL}")
        return DEFAULT_CONFIG.copy()
    except ValueError as e:
        print(f"{Fore.RED}Error: Invalid configuration in '{config_path}': {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Using default settings.{Style.RESET_ALL}")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f"{Fore.RED}Error: Could not load '{config_path}': {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Using default settings.{Style.RESET_ALL}")
        return DEFAULT_CONFIG.copy()


def is_audio_file(file_path):
    """Check if the file is an audio-only file."""
    return file_path.lower().endswith(AUDIO_EXTENSIONS)


def is_video_file(file_path):
    """Check if the file is a video file."""
    return file_path.lower().endswith(VIDEO_EXTENSIONS)

def process_file(input_file, keep_temp=False, duration=None, progress_callback=None):
    """
    Process a video or audio file to separate vocals.
    Handles both video files (creates new video with vocals) and audio files (creates vocals-only audio).
    """
    def update_progress(step, progress):
        if progress_callback:
            progress_callback(step, progress)

    is_audio_only = is_audio_file(input_file)
    if not os.path.exists(input_file):
        print(f"{Fore.RED}Error: Input video file '{input_file}' not found.{Style.RESET_ALL}")
        return False
    
    # Ensure local temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    original_duration = get_audio_duration(input_file)
    if original_duration is None:
        print(f"{Fore.YELLOW}Warning: Could not determine audio duration for the original video.{Style.RESET_ALL}")

    print(f"\n{Back.MAGENTA}{Fore.WHITE}# SISTEMSKA PROVJERA {Style.RESET_ALL}")

    cuda_is_available = check_gpu_cuda_support()

    if not cuda_is_available:
        print(f"{Fore.RED}GPU akceleracija nije podržana.{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}GPU akceleracija podržana.{Style.RESET_ALL}")

    temp_audio_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=TEMP_DIR)
    temp_audio_wav_path = temp_audio_wav_file.name
    temp_audio_wav_file.close()

    base_audio_name_no_ext = os.path.splitext(os.path.basename(temp_audio_wav_path))[0]

    spleeter_out_path = "spleeter_out"
    demucs_base_out_path = "demucs_out"

    temp_vocal_mixture_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=TEMP_DIR)
    vocal_mixture_wav_path = temp_vocal_mixture_wav_file.name
    temp_vocal_mixture_wav_file.close()

    temp_aligned_spleeter_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_spleeter.wav", delete=False, dir=TEMP_DIR)
    aligned_spleeter_vocals_path = temp_aligned_spleeter_vocals.name
    temp_aligned_spleeter_vocals.close()

    temp_aligned_demucs_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_demucs.wav", delete=False, dir=TEMP_DIR)
    aligned_demucs_vocals_path = temp_aligned_demucs_vocals.name
    temp_aligned_demucs_vocals.close()

    temp_spleeter_segments_dir = None
    spleeter_vocal_wav_path = None
    temp_demucs_segments_dir = None
    combined_vocals_aac_path = None

    try:
        file_type = "audio" if is_audio_only else "video"
        print(f"\n{Back.YELLOW}{Fore.BLACK}# MUSIC REMOVAL STARTED FOR {input_file} ({file_type} file) ---")
        print(f"{Style.RESET_ALL}")

        # Step 0: Audio Track Selection
        selected_track_index = None
        update_progress("Scanning audio tracks", 5)
        audio_tracks = get_audio_tracks(input_file)

        if not audio_tracks:
            update_progress("Error: No audio tracks found", 0)
            print(f"{Fore.RED}Error: No audio tracks found in '{input_file}'. Aborting.{Style.RESET_ALL}")
            return False

        if not is_audio_only:
            # Language priorities for automatic selection
            priority_languages = ["hr", "hrv", "sr","jpn"]
            selected_track = None

            # Try to find a track matching priority languages
            for lang in priority_languages:
                for track in audio_tracks:
                    if track['language'].lower() == lang:
                        selected_track = track
                        break
                if selected_track:
                    break
            
            # Default to first track if no match found
            if not selected_track:
                selected_track = audio_tracks[0]
            
            selected_track_index = selected_track['index']
            print(f"{Fore.GREEN}Selected audio track: Language: {selected_track['language']}, Stream Index: {selected_track['index']}{Style.RESET_ALL}\n")
        else:
            # For audio-only files, we use the first available audio track (usually only one)
            selected_track_index = audio_tracks[0]['index']
            print(f"{Fore.GREEN}Processing audio file with track index: {selected_track_index}{Style.RESET_ALL}\n")

        # Step 1: Export Source to High-Quality WAV for processing
        print(f"{Fore.CYAN}1. Extracting audio to temporary WAV: {temp_audio_wav_path}...{Style.RESET_ALL}")
        update_progress("Extracting audio", 10)
        ffmpeg_cmd = [FFMPEG_EXE, "-y","-loglevel","error", "-i", input_file]
        if duration:
            ffmpeg_cmd.extend(["-t", str(duration)])
            print(f"{Fore.YELLOW}Limiting processing to first {duration} seconds.{Style.RESET_ALL}")
            
        if selected_track_index is not None:
            ffmpeg_cmd.extend(["-map", f"0:{selected_track_index}"])
        
        # Downmix to stereo (Demucs/Spleeter prefer 2 channels)
        ffmpeg_cmd.extend(["-ac", "2"])
        ffmpeg_cmd.append(temp_audio_wav_path)
        
        print(f"{Fore.MAGENTA}Executing: {' '.join(ffmpeg_cmd)}\n")
        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"{Fore.GREEN}Audio extraction complete.\n{Style.RESET_ALL}")
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error extracting audio: {e}{Style.RESET_ALL}")
            return False

        # Step 2 & 3: Run AI Source Separation Models
        settings = load_config('video.json')
        demucs_workers = settings.get('processing', {}).get('demucs_workers', 2)

        # Both models return (path_to_wav, temp_segments_dir)
        update_progress("Running Spleeter", 20)
        spleeter_vocal_wav_path, temp_spleeter_segments_dir = separate_with_spleeter(temp_audio_wav_path, spleeter_out_path, base_audio_name_no_ext)
        update_progress("Running Demucs", 50)
        demucs_vocal_wav_path, temp_demucs_segments_dir = separate_with_demucs(
            temp_audio_wav_path, demucs_base_out_path, base_audio_name_no_ext, max_workers=demucs_workers
        )

        # Step 4: Logic for Alinging and Mixing the results
        print(f"{Fore.CYAN}4. Aligning and combining Spleeter (WAV) and Demucs (WAV) vocals...{Style.RESET_ALL}\n")

        spleeter_input_exists = spleeter_vocal_wav_path and os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0
        demucs_input_exists = demucs_vocal_wav_path and os.path.exists(demucs_vocal_wav_path) and os.path.getsize(demucs_vocal_wav_path) > 0

        if not spleeter_input_exists and not demucs_input_exists:
            print(f"{Fore.RED}Error: Neither Spleeter nor Demucs vocal files were successfully generated.{Style.RESET_ALL}")
            return False
        
        # Branching logic for when only one model succeeds
        elif not spleeter_input_exists:
            print(f"{Fore.YELLOW}Only Demucs vocals found. Using Demucs vocals directly.{Style.RESET_ALL}")
            try:
                # Copy Demucs WAV to our vocal mixture path (still WAV)
                shutil.copy2(demucs_vocal_wav_path, vocal_mixture_wav_path)
                print(f"{Fore.GREEN}Demucs vocals ready for mixing.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error copying Demucs vocals: {e}{Style.RESET_ALL}")
                return False
        elif not demucs_input_exists:
            print(f"{Fore.YELLOW}Only Spleeter vocals found. Using Spleeter vocals directly.{Style.RESET_ALL}")
            try:
                shutil.copy2(spleeter_vocal_wav_path, vocal_mixture_wav_path)
                print(f"{Fore.GREEN}✔ Spleeter vocals ready for mixing.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error copying Spleeter vocals: {e}{Style.RESET_ALL}")
                return False
        else:
            # When both exist, perform cross-correlation alignment to fix any millisecond offsets
            update_progress("Aligning audio tracks", 80)
            aligned_spleeter, aligned_demucs = align_audio_tracks(spleeter_vocal_wav_path, demucs_vocal_wav_path, aligned_spleeter_vocals_path, aligned_demucs_vocals_path)

            if aligned_spleeter and aligned_demucs:
                # Mix both aligned tracks into a temporary file
                temp_mixed_wav_path = tempfile.NamedTemporaryFile(suffix="_mixed.wav", delete=False)
                temp_mixed_wav_path.close()
                
                try:
                    # Equal weight mix (0.5 each)
                    update_progress("Mixing vocals", 90)
                    mixed_result = mix_audio_tracks(aligned_spleeter, aligned_demucs, vocal_mixture_wav_path, volume1=0.5, volume2=0.5)
                    
                    if mixed_result:
                        print(f"\n{Fore.GREEN}✔ Vocals combined successfully.{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Error: Mixing of aligned vocal tracks failed.{Style.RESET_ALL}")
                        return False
                except subprocess.CalledProcessError as e:
                    print(f"{Fore.RED}Error with mixed audio conversion: {e}{Style.RESET_ALL}")
                    return False
                finally:
                    if os.path.exists(temp_mixed_wav_path.name):
                        try:
                            os.remove(temp_mixed_wav_path.name)
                        except OSError:
                            pass
            else:
                print(f"{Fore.RED}Error: Alignment failed. Cannot combine vocal tracks.{Style.RESET_ALL}")
                return False

        # Smarter synchronization: Only pad the start based on detected lag, then pad the end.
        original_audio_duration = get_audio_duration(temp_audio_wav_path)
        processed_audio_duration = get_audio_duration(vocal_mixture_wav_path)
        
        if original_audio_duration and processed_audio_duration:
            import soundfile as sf
            
            # Step 4b: Detect REAL lag between original and processed mixture
            print(f"{Fore.CYAN}4b. Final synchronization check...{Style.RESET_ALL}")
            try:
                # Read original (mono subset for check) and processed
                ref_audio, ref_sr = sf.read(temp_audio_wav_path)
                proc_audio, proc_sr = sf.read(vocal_mixture_wav_path)
                
                # We only need to check the beginning for lag
                _, lag_ms = calculate_audio_lag(proc_audio, proc_sr, ref_audio, ref_sr)
                
                print(f"{Fore.BLUE}Detected start lag: {lag_ms:.2f} ms{Style.RESET_ALL}")
                
                # If lag is very large (e.g. > 1s), it's likely a misdetection or a huge error
                # Usually AI lag is < 50ms.
                if abs(lag_ms) > 1000:
                    print(f"{Fore.YELLOW}Warning: Detected lag is suspiciously large. Limiting to 0.{Style.RESET_ALL}")
                    lag_ms = 0
                
                adj_temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=TEMP_DIR)
                adj_temp_path = adj_temp_file.name
                adj_temp_file.close()

                # Build filter chain: 
                # 1. adelay for the start lag
                # 2. apad to fill the remaining duration at the end
                # 3. atrim to ensure it's not LONGER than original
                
                filter_parts = []
                if lag_ms > 0:
                    filter_parts.append(f"adelay={int(lag_ms)}|{int(lag_ms)}")
                
                # Pad to original duration
                filter_parts.append(f"apad=whole_dur={original_audio_duration}")
                
                # Hard trim at original duration
                filter_parts.append(f"atrim=0:{original_audio_duration}")
                
                adjust_cmd = [
                    FFMPEG_EXE, "-y", "-loglevel", "error",
                    "-i", vocal_mixture_wav_path,
                    "-af", ",".join(filter_parts),
                    adj_temp_path
                ]
                
                print(f"{Fore.MAGENTA}Applying sync filters: {','.join(filter_parts)}{Style.RESET_ALL}")
                subprocess.run(adjust_cmd, check=True)
                
                os.remove(vocal_mixture_wav_path)
                os.rename(adj_temp_path, vocal_mixture_wav_path)
                print(f"{Fore.GREEN}✔ Final synchronization complete.{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.RED}Error during final sync: {e}. Keeping original mixture.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Could not verify audio durations for final sync.{Style.RESET_ALL}")

        # Step 5: Convert final mixture to ultimate output format
        temp_combined_vocals_aac_file = tempfile.NamedTemporaryFile(suffix=".aac", delete=False, dir=TEMP_DIR)
        final_mixture_aac_path = temp_combined_vocals_aac_file.name
        temp_combined_vocals_aac_file.close()

        update_progress("Finalizing audio format", 95)
        success = convert_audio_with_ffmpeg(vocal_mixture_wav_path, final_mixture_aac_path, normalize_audio=True)
        if not success:
            print(f"{Fore.RED}Error finalizing output audio format.{Style.RESET_ALL}")
            return False
            
        combined_vocals_aac_path = final_mixture_aac_path

        output_folder = "nomusic"
        os.makedirs(output_folder, exist_ok=True)
        
        # Load and validate configuration
        settings = load_config('video.json')
        
        video_settings = settings.get('video', {})
        audio_settings = settings.get('audio', {})
        output_settings = settings.get('output', {})

        audio_codec = audio_settings.get('codec', 'aac')
        audio_bitrate = audio_settings.get('bitrate')
        
        # Strip UUID from input filename if present (36 chars uuid + 1 char underscore)
        raw_name = os.path.basename(input_file)
        if "_" in raw_name and len(raw_name.split("_")[0]) == 36:
            clean_name = "_".join(raw_name.split("_")[1:])
        else:
            clean_name = raw_name
            
        base_filename = f"nomusic_{os.path.splitext(clean_name)[0]}"
        
        try:
            if is_audio_only:
                # For audio-only files, just output the processed audio
                print(f"\n{Fore.CYAN}5. Creating final audio file...{Style.RESET_ALL}")
                
                # Determine output format based on input or config
                audio_output_format = "mp3"  # Default for audio-only
                if input_file.lower().endswith('.flac'):
                    audio_output_format = "flac"
                elif input_file.lower().endswith('.wav'):
                    audio_output_format = "wav"
                elif input_file.lower().endswith('.m4a'):
                    audio_output_format = "m4a"
                
                output_audio = os.path.join(output_folder, f"{base_filename}_vocals.{audio_output_format}")
                print(f"{Fore.CYAN}Output audio file: {output_audio}{Style.RESET_ALL}")
                
                final_ffmpeg_cmd = [
                    FFMPEG_EXE,
                    "-loglevel", "error",
                    "-y",
                    "-i", combined_vocals_aac_path,
                ]
                
                if audio_output_format == "flac":
                    final_ffmpeg_cmd.extend(["-c:a", "flac"])
                elif audio_output_format == "wav":
                    final_ffmpeg_cmd.extend(["-c:a", "pcm_s16le"])
                else:
                    final_ffmpeg_cmd.extend(["-c:a", audio_codec])
                    if audio_bitrate:
                        final_ffmpeg_cmd.extend(["-b:a", audio_bitrate])
                
                final_ffmpeg_cmd.append(output_audio)
                
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(final_ffmpeg_cmd)}")
                subprocess.run(final_ffmpeg_cmd, check=True)
                print(f"\n{Fore.GREEN}✔ Successfully created {output_audio}{Style.RESET_ALL}")
                
                # Get final audio duration and compare
                final_duration = get_audio_duration(output_audio)
                if final_duration is not None and original_duration is not None:
                    duration_diff = abs(original_duration - final_duration)
                    print(f"{Fore.BLUE}Final audio duration: {final_duration:.2f} seconds{Style.RESET_ALL}")
                    if duration_diff > 1:
                        print(f"{Fore.YELLOW}Warning: Duration difference of {duration_diff:.2f} seconds between original and final audio.{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.GREEN}Audio duration is consistent.{Style.RESET_ALL}")
                
                return output_audio
            else:
                # For video files, create new video with vocals
                print(f"\n{Fore.CYAN}5. Creating final video...{Style.RESET_ALL}")
                
                video_codec_setting = video_settings.get('codec', 'copy')
                video_bitrate = video_settings.get('bitrate')
                output_format = output_settings.get('format', 'mp4')

                output_video = os.path.join(output_folder, f"{base_filename}.{output_format}")
                print(f"{Fore.CYAN}Output video file: {output_video}{Style.RESET_ALL}")

                video_codec = video_codec_setting

                final_ffmpeg_cmd = [
                    FFMPEG_EXE,
                    "-loglevel", "error",
                    "-y",
                    "-i", input_file,
                    "-i", combined_vocals_aac_path,
                    "-vf", "scale=1920:1080",
                    "-c:v", video_codec,
                ]
                if video_bitrate:
                    final_ffmpeg_cmd.extend(["-b:v", video_bitrate])
                
                final_ffmpeg_cmd.extend([
                    "-c:a", audio_codec,
                ])
                if audio_bitrate:
                    final_ffmpeg_cmd.extend(["-b:a", audio_bitrate])

                final_ffmpeg_cmd.extend([
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest",
                    "-f", output_format,
                    output_video
                ])
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(final_ffmpeg_cmd)}")
                update_progress("Finalizing output", 95)
                subprocess.run(final_ffmpeg_cmd, check=True)
                update_progress("Completed", 100)
                print(f"\n{Fore.GREEN}✔ Successfully created {output_video}{Style.RESET_ALL}")

                # Get final audio duration and compare
                final_duration = get_audio_duration(output_video)
                if final_duration is not None and original_duration is not None:
                    duration_diff = abs(original_duration - final_duration)
                    print(f"{Fore.BLUE}Final video audio duration: {final_duration:.2f} seconds{Style.RESET_ALL}")
                    if duration_diff > 1:
                        print(f"{Fore.YELLOW}Warning: Duration difference of {duration_diff:.2f} seconds between original and final video.{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.GREEN}Audio duration is consistent.{Style.RESET_ALL}")

                return output_video
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}✖Error creating final output: {e}{Style.RESET_ALL}")
            return False

    finally:
        if not keep_temp:
            print(f"\n{Fore.CYAN}--- Cleanup of temporary files ---")
            for f_path in [temp_audio_wav_path, combined_vocals_aac_path, 
                           aligned_spleeter_vocals_path, aligned_demucs_vocals_path,
                           vocal_mixture_wav_path]:
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
        else:
            print(f"\n{Fore.YELLOW}--- Skipping cleanup of temporary files ---")
            print(f"Temporary audio WAV file: {temp_audio_wav_path}")
            print(f"Combined vocals AAC file: {combined_vocals_aac_path}")
            print(f"Aligned Spleeter vocals: {aligned_spleeter_vocals_path}")
            print(f"Aligned Demucs vocals: {aligned_demucs_vocals_path}")
            if temp_spleeter_segments_dir:
                print(f"Spleeter segments directory: {temp_spleeter_segments_dir}")
            if temp_demucs_segments_dir:
                print(f"Demucs segments directory: {temp_demucs_segments_dir}")
            print(f"Spleeter output path: {spleeter_out_path}")
            print(f"Demucs output path: {demucs_base_out_path}")
        print(f"{Fore.CYAN}--- Processing complete ---")