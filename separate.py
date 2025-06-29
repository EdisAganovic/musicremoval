import subprocess
import os
import tempfile
import shutil
import platform
import math # Import math for ceil

# Add colorama library for text colors and background colors
from colorama import Fore, Back, Style, init, deinit

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Apply yellow color for warnings
    print(f"{Fore.YELLOW}Warning: PyTorch is not installed. GPU/CUDA support cannot be checked or utilized by Demucs/Spleeter.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Please install PyTorch with GPU support if you intend to use your NVIDIA GPU:{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 (or appropriate CUDA version){Style.RESET_ALL}")

# --- Add pydub, numpy, scipy, soundfile imports and checks ---
PYDUB_AVAILABLE = False
NUMPY_SCIPY_AVAILABLE = False
SOUNDFILE_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    print(f"{Fore.YELLOW}Warning: pydub is not installed. Will attempt soundfile for alignment, but pydub can be useful for other audio manipulations.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Please install pydub: pip install pydub{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Note: pydub also requires ffmpeg to be installed and in your PATH.{Style.RESET_ALL}")

try:
    import numpy as np
    from scipy import signal
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True # soundfile is used for loading audio for numpy/scipy
    NUMPY_SCIPY_AVAILABLE = True
except ImportError:
    print(f"{Fore.YELLOW}Warning: numpy, scipy, or soundfile are not installed. Cannot perform dynamic audio alignment.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Please install them: pip install numpy scipy soundfile{Style.RESET_ALL}")
# --- End pydub, numpy, scipy, soundfile imports and checks ---


def get_audio_duration(file_path):
    """
    Gets the duration of an audio file using ffprobe.
    Returns duration in seconds as float, or None if an error occurs.
    """
    try:
        # Use ffprobe to get duration
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error: ffprobe failed to get duration for {file_path}. Is ffprobe installed and in PATH? Error: {e}{Style.RESET_ALL}")
        return None
    except ValueError:
        print(f"{Fore.RED}Error: ffprobe returned non-numeric duration for {file_path}.{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred while getting audio duration for {file_path}: {e}{Style.RESET_ALL}")
        return None


def check_gpu_cuda_support():
    """
    Checks for PyTorch CUDA availability and prints GPU information.
    Returns True if CUDA is available, False otherwise.
    """
    # Apply cyan color for headers--
    print(f"\n{Fore.CYAN}2. Provjera GPU/CUDA podrške{Style.RESET_ALL}")
    if not TORCH_AVAILABLE:
        # Apply yellow color for warnings
        print(f"{Fore.YELLOW}PyTorch is not installed. Cannot check for CUDA support.{Style.RESET_ALL}")
        return False

    if torch.cuda.is_available():
        # Apply green color for success messages
        print(f"{Fore.GREEN}CUDA Version: {torch.version.cuda} # {torch.cuda.get_device_name(0)} ({torch.cuda.device_count()}){Style.RESET_ALL}")
        return True
    else:
        # Apply red color for errors, yellow for suggestions
        print(f"{Fore.RED}PyTorch CUDA is NOT AVAILABLE.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  - Check if NVIDIA drivers are installed.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  - Check if CUDA Toolkit is installed and its paths are configured correctly.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  - Remove pip uninstall torch torchaudio torchvision and install again with CUDA support from PyTorch website.{Style.RESET_ALL}")
        print(f"{Fore.RED}Demucs and Spleeter will run on CPU, which can be significantly slower.{Style.RESET_ALL}")
        return False

def _check_program_installed(program_name):
    """Provjera dodatnih alata """
    if shutil.which(program_name):
        # Apply green color for success
        print(f"{Fore.GREEN}'{program_name}' instaliran.{Style.RESET_ALL}")
        return True
    else:
        # Apply red color for errors
        print(f"{Fore.RED}Error: '{program_name}' not found in system PATH.{Style.RESET_ALL}")
        print(f"{Fore.RED}Please ensure '{program_name}' is installed and its executable directory is added to your system's PATH environment variable.{Style.RESET_ALL}")
        return False

def align_audio_tracks(track1_path, track2_path, output_aligned_track1_path, output_aligned_track2_path):
    """
    Aligns two audio tracks using cross-correlation.
    Pads the beginning of the track that starts earlier.
    Saves the aligned tracks to new paths.

    Returns the paths to the aligned tracks, or None if alignment fails.
    """
    if not NUMPY_SCIPY_AVAILABLE:
        print(f"{Fore.RED}Cannot align audio tracks: numpy, scipy, or soundfile not available.{Style.RESET_ALL}")
        return track1_path, track2_path # Return original paths if tools are missing

    print(f"\n{Fore.CYAN}Attempting to align audio tracks using cross-correlation...{Style.RESET_ALL}")
    try:
        # Load audio files
        audio1, sr1 = sf.read(track1_path)
        audio2, sr2 = sf.read(track2_path)

        if sr1 != sr2:
            print(f"{Fore.YELLOW}Warning: Sample rates differ ({sr1} vs {sr2}). Resampling for alignment.{Style.RESET_ALL}")
            # If sample rates differ, resample one to match the other.
            # For simplicity, let's resample track2 to track1's SR.
            # A more robust solution might resample both to a common SR or handle this with ffmpeg.
            # For now, if they significantly differ, cross-correlation might fail.
            # This is a basic approach and might not be perfect for large SR differences.
            if sr1 < sr2:
                # If sr1 is lower, resample track2 down to sr1
                num = int(audio2.shape[0] * sr1 / sr2)
                audio2 = signal.resample(audio2, num)
            elif sr2 < sr1:
                # If sr2 is lower, resample track1 down to sr2
                num = int(audio1.shape[0] * sr2 / sr1)
                audio1 = signal.resample(audio1, num)
                sr1 = sr2 # Update sr1 to match
        
        # Convert to mono if stereo
        if audio1.ndim > 1:
            audio1 = audio1.mean(axis=1)
        if audio2.ndim > 1:
            audio2 = audio2.mean(axis=1)

        # Pad the shorter audio to match the length of the longer one for correlation
        len1 = len(audio1)
        len2 = len(audio2)
        max_len = max(len1, len2)

        padded_audio1 = np.pad(audio1, (0, max_len - len1), 'constant')
        padded_audio2 = np.pad(audio2, (0, max_len - len2), 'constant')

        # Compute cross-correlation
        correlation = signal.correlate(padded_audio1, padded_audio2, mode='full')
        
        # Find the lag with the maximum correlation
        # The lag array goes from -(N-1) to (N-1) where N is the length of the signals.
        # The index where max correlation occurs corresponds to the shift.
        delay_samples = np.argmax(correlation) - (max_len - 1)

        delay_ms = (delay_samples / sr1) * 1000 # Delay in milliseconds

        print(f"{Fore.BLUE}Calculated audio delay: {delay_ms:.2f} ms ({delay_samples} samples){Style.RESET_ALL}")

        # Apply padding to align tracks
        aligned_audio1 = audio1
        aligned_audio2 = audio2

        if delay_samples > 0:
            # Track1 starts earlier, pad Track2
            print(f"{Fore.BLUE}Padding Track 2 (Demucs) by {delay_ms:.2f} ms.{Style.RESET_ALL}")
            aligned_audio2 = np.pad(audio2, (delay_samples, 0), 'constant')
            # Ensure both are at least as long as the original longer track + delay
            aligned_audio1 = np.pad(audio1, (0, max(0, len(aligned_audio2) - len(audio1))), 'constant')
        elif delay_samples < 0:
            # Track2 starts earlier, pad Track1
            print(f"{Fore.BLUE}Padding Track 1 (Spleeter) by {-delay_ms:.2f} ms.{Style.RESET_ALL}")
            aligned_audio1 = np.pad(audio1, (-delay_samples, 0), 'constant')
            # Ensure both are at least as long as the original longer track + delay
            aligned_audio2 = np.pad(audio2, (0, max(0, len(aligned_audio1) - len(audio2))), 'constant')
        else:
            print(f"{Fore.GREEN}Tracks are already aligned. No padding needed.{Style.RESET_ALL}")
            # Ensure they are the same length if they were originally slightly different
            max_orig_len = max(len1, len2)
            aligned_audio1 = np.pad(audio1, (0, max(0, max_orig_len - len1)), 'constant')
            aligned_audio2 = np.pad(audio2, (0, max(0, max_orig_len - len2)), 'constant')

        # Save aligned tracks
        sf.write(output_aligned_track1_path, aligned_audio1, sr1)
        sf.write(output_aligned_track2_path, aligned_audio2, sr2)

        print(f"{Fore.GREEN}\N{check mark} Audio tracks aligned and saved.{Style.RESET_ALL}")
        return output_aligned_track1_path, output_aligned_track2_path

    except FileNotFoundError:
        print(f"{Fore.RED}Error: One of the audio files for alignment was not found.{Style.RESET_ALL}")
        return None, None
    except Exception as e:
        print(f"{Fore.RED}An error occurred during audio alignment: {e}{Style.RESET_ALL}")
        return None, None


def process_video(input_file):
    if not os.path.exists(input_file):
        # Apply red color for errors
        print(f"{Fore.RED}Error: Input video file '{input_file}' not found.{Style.RESET_ALL}")
        return False
    print(f"\n{Back.MAGENTA}{Fore.WHITE}# SISTEMSKA PROVJERA {Style.RESET_ALL}")
    # --- Check required programs at the start ---
    # Apply cyan color for headers
    print(f"\n{Fore.CYAN}1. Provjera dodatnih alata da li su instalirani{Style.RESET_ALL}")
    if not _check_program_installed("ffmpeg"):
        return False
    if not _check_program_installed("spleeter"):
        return False
    if not _check_program_installed("demucs"):
        return False

    # --- Check GPU/CUDA support ---
    cuda_is_available = check_gpu_cuda_support()

    if not cuda_is_available:
        # Apply yellow color for warnings/notes
        print(f"{Fore.RED}GPU akceleracija nije podržana.{Style.RESET_ALL}")
    else:
        # Apply green color for positive notes
        print(f"{Fore.GREEN}GPU akceleracija podržana.{Style.RESET_ALL}")


    # --- Define all file and directory paths ---

    # Temporary file for the initially extracted audio (will be cleaned up automatically)
    temp_audio_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_audio_wav_path = temp_audio_wav_file.name
    temp_audio_wav_file.close() # Close the file handle immediately so other processes can access it

    # Get the base name of the temporary WAV file (Spleeter/Demucs use this for subfolders)
    base_audio_name_no_ext = os.path.splitext(os.path.basename(temp_audio_wav_path))[0]

    spleeter_out_path = "spleeter_out"
    # Demucs will create 'htdemucs' inside 'separated' by default when using -o
    demucs_base_out_path = "demucs_out"

    # Paths to the vocal stems produced by Spleeter and Demucs within their respective output folders
    demucs_vocal_wav_path = os.path.join(demucs_base_out_path, "htdemucs", base_audio_name_no_ext, "vocals.wav")

    # Temporary file for the combined vocals (will be cleaned up automatically)
    temp_combined_vocals_aac_file = tempfile.NamedTemporaryFile(suffix=".aac", delete=False)
    combined_vocals_aac_path = temp_combined_vocals_aac_file.name
    temp_combined_vocals_aac_file.close()

    # Temporary files for aligned vocals before combining
    temp_aligned_spleeter_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_spleeter.wav", delete=False)
    aligned_spleeter_vocals_path = temp_aligned_spleeter_vocals.name
    temp_aligned_spleeter_vocals.close()

    temp_aligned_demucs_vocals = tempfile.NamedTemporaryFile(suffix="_aligned_demucs.wav", delete=False)
    aligned_demucs_vocals_path = temp_aligned_demucs_vocals.name
    temp_aligned_demucs_vocals.close()


    # Initialize temp_spleeter_segments_dir outside try to ensure it's in scope for finally
    temp_spleeter_segments_dir = None
    spleeter_vocal_wav_path = None # Initialize this here, it will be set later based on Spleeter's output

    try:
        # Apply cyan color for headers
        print(f"\n{Back.YELLOW}{Fore.BLACK}# UKLANJANJE MUZIKE ZAPOČETO ZA FAJL: {input_file} ---{Style.RESET_ALL}\n")

        # 1. Extract audio from MP4 to WAV using ffmpeg
        print(f"{Fore.CYAN}1. Extracting audio to temporary WAV: {temp_audio_wav_path}...{Style.RESET_ALL}")
        ffmpeg_cmd = ["ffmpeg", "-y","-loglevel","error", "-i", input_file, temp_audio_wav_path]
        print(f"{Fore.MAGENTA}Executing: {' '.join(ffmpeg_cmd)}\n") # Keep command execution line uncolored
        try:
            subprocess.run(ffmpeg_cmd, check=True)
            # Apply green color for success
            print(f"{Fore.GREEN}Audio extraction complete.\n{Style.RESET_ALL}")
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error extracting audio: {e}{Style.RESET_ALL}")
            return False


        # 2. Separate audio into stems using spleeter (with potential segmentation)
        print(f"{Fore.CYAN}2. Separating with Spleeter...{Style.RESET_ALL}")
        try:
            os.makedirs(spleeter_out_path, exist_ok=True)

            audio_duration = get_audio_duration(temp_audio_wav_path)
            if audio_duration is None:
                print(f"{Fore.RED}Failed to get audio duration, cannot proceed with Spleeter separation.{Style.RESET_ALL}")
                spleeter_vocal_wav_path = None # Ensure it's marked as unavailable
            else:
                SPLEETER_SEGMENT_DURATION_SECONDS = 600 # 10 minutes

                if audio_duration > SPLEETER_SEGMENT_DURATION_SECONDS:
                    print(f"\n{Fore.YELLOW}Audio duration ({audio_duration:.2f}s) exceeds Spleeter's typical 10-minute limit. Splitting audio for Spleeter...{Style.RESET_ALL}\n")
                    temp_spleeter_segments_dir = tempfile.mkdtemp() # Dir for split audio files and concat list
                    spleeter_segment_vocal_paths = []
                    split_audio_paths = []

                    current_start_time = 0
                    segment_index = 0

                    # Split the audio into segments
                    while current_start_time < audio_duration:
                        segment_duration = min(SPLEETER_SEGMENT_DURATION_SECONDS, audio_duration - current_start_time)
                        segment_filename = f"part_{segment_index:03d}.wav"
                        segment_output_path = os.path.join(temp_spleeter_segments_dir, segment_filename)

                        ffmpeg_split_cmd = [
                            "ffmpeg", "-y", "-loglevel", "error",
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

                    print(f"\n{Fore.GREEN}\N{check mark} Audio splitted into {len(split_audio_paths)} segments for Spleeter.{Style.RESET_ALL}")

                    # Process each segment with Spleeter
                    for i, segment_path in enumerate(split_audio_paths):
                        segment_base_name = os.path.splitext(os.path.basename(segment_path))[0]
                        spleeter_segment_out_sub_path = os.path.join(spleeter_out_path, segment_base_name)
                        
                        spleeter_cmd = ["spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, segment_path]
                        print(f"\n{Fore.MAGENTA}Processing segment {i+1}/{len(split_audio_paths)} with Spleeter: \n{' '.join(spleeter_cmd)}{Style.RESET_ALL}")
                        subprocess.run(spleeter_cmd, check=True)

                        segment_vocal_path = os.path.join(spleeter_segment_out_sub_path, "vocals.wav")
                        if os.path.exists(segment_vocal_path) and os.path.getsize(segment_vocal_path) > 0:
                            spleeter_segment_vocal_paths.append(segment_vocal_path)
                        else:
                            print(f"{Fore.YELLOW}Warning: Spleeter vocals for segment {segment_base_name} not found or empty at {segment_vocal_path}. Skipping this segment.{Style.RESET_ALL}")

                    if not spleeter_segment_vocal_paths:
                        print(f"{Fore.RED}Error: No Spleeter vocal segments were successfully generated. Spleeter output will not be used for combination.{Style.RESET_ALL}")
                        spleeter_vocal_wav_path = None # Indicate failure to get any Spleeter vocals
                    else:
                        # Concatenate all Spleeter vocal segments
                        concat_list_path = os.path.join(temp_spleeter_segments_dir, "concat_list.txt")
                        with open(concat_list_path, "w") as f:
                            for p in spleeter_segment_vocal_paths:
                                f.write(f"file '{os.path.abspath(p)}'\n") # Use absolute path for concat for robustness

                        final_spleeter_vocals_filename = "concatenated_spleeter_vocals.wav"
                        final_spleeter_vocals_temp_path = os.path.join(temp_spleeter_segments_dir, final_spleeter_vocals_filename)
                        
                        ffmpeg_concat_cmd = [
                            "ffmpeg", "-y", 
                            "-loglevel", "error",
                            "-f", "concat",
                            "-safe", "0", # Required for absolute paths or paths outside current directory
                            "-i", concat_list_path,
                            "-c", "copy", # Copy streams without re-encoding for speed and quality
                            final_spleeter_vocals_temp_path
                        ]
                        print(f"\nJoining Spleeter vocal segments to: {final_spleeter_vocals_temp_path}")
                        subprocess.run(ffmpeg_concat_cmd, check=True)
                        spleeter_vocal_wav_path = final_spleeter_vocals_temp_path
                        print(f"\n{Fore.GREEN}\N{check mark} All Spleeter vocal segments joined successfully.{Style.RESET_ALL}")
                        
                else:
                    # Audio is short enough, run Spleeter directly on the original temp_audio_wav_path
                    spleeter_cmd = ["spleeter", "separate", "-p", "spleeter:2stems", "-o", spleeter_out_path, temp_audio_wav_path]
                    print(f"{Fore.MAGENTA}Executing Spleeter directly: {' '.join(spleeter_cmd)}{Style.RESET_ALL}\n")
                    subprocess.run(spleeter_cmd, check=True)
                    spleeter_vocal_wav_path = os.path.join(spleeter_out_path, base_audio_name_no_ext, "vocals.wav")
                    print(f"{Fore.GREEN}Spleeter separation complete. Output in: {spleeter_out_path}{Style.RESET_ALL}")
                
            if spleeter_vocal_wav_path and not (os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0):
                print(f"{Fore.YELLOW}Warning: Final Spleeter vocals not found or empty at {spleeter_vocal_wav_path}. This might be expected if Spleeter failed.{Style.RESET_ALL}")
                spleeter_vocal_wav_path = None # Explicitly set to None if file is missing/empty

        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error with spleeter separation: {e}{Style.RESET_ALL}")
            spleeter_vocal_wav_path = None # Ensure it's marked as unavailable
        except Exception as e: # Catch other potential errors, e.g., file operations
            print(f"{Fore.RED}An unexpected error occurred during Spleeter processing: {e}{Style.RESET_ALL}")
            spleeter_vocal_wav_path = None # Ensure it's marked as unavailable


        # 3. Separate audio into stems using Demucs (htdemucs model)
        print(f"\n{Fore.CYAN}3. Separating with Demucs (htdemucs model) into: {demucs_base_out_path}...{Style.RESET_ALL}")
        try:
            os.makedirs(demucs_base_out_path, exist_ok=True) # Ensure the base output directory exists

            demucs_cmd = [
                "demucs",
                # "--two-stems=vocals", This will not be faster
                #"--mp3", # Output MP3 files for stems
                "-n","htdemucs",
                "-o", demucs_base_out_path, # Specify the root output directory
                temp_audio_wav_path
            ]
            print(f"{Fore.MAGENTA}Executing: {' '.join(demucs_cmd)}\n{Style.RESET_ALL}") # Keep command execution line uncolored
            subprocess.run(demucs_cmd, check=True)
            # Apply green color for success
            print(f"\n{Fore.GREEN}\N{check mark} Demucs separation complete. Output in: {demucs_base_out_path}\n{Style.RESET_ALL}")

            if not os.path.exists(demucs_vocal_wav_path) or os.path.getsize(demucs_vocal_wav_path) == 0:
                print(f"{Fore.YELLOW}Warning: Demucs vocals not found or empty at {demucs_vocal_wav_path}.{Style.RESET_ALL}")

        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error with demucs separation: {e}{Style.RESET_ALL}")
            demucs_vocal_wav_path = None # Ensure it's marked as unavailable


        # 4. Align and Combine the two vocal files using ffmpeg (audio mixing)
        print(f"{Fore.CYAN}4. Aligning and combining Spleeter (WAV) and Demucs (WAV) vocals into temporary AAC: {combined_vocals_aac_path}...{Style.RESET_ALL}")

        spleeter_input_exists = spleeter_vocal_wav_path and os.path.exists(spleeter_vocal_wav_path) and os.path.getsize(spleeter_vocal_wav_path) > 0
        demucs_input_exists = demucs_vocal_wav_path and os.path.exists(demucs_vocal_wav_path) and os.path.getsize(demucs_vocal_wav_path) > 0

        if not spleeter_input_exists and not demucs_input_exists:
            print(f"{Fore.RED}Error: Neither Spleeter nor Demucs vocal files were successfully generated. Cannot combine.{Style.RESET_ALL}")
            return False
        elif not spleeter_input_exists:
            print(f"{Fore.YELLOW}Only Demucs vocals found. Using Demucs vocals directly for the combined track.{Style.RESET_ALL}")
            try:
                # Re-encode Demucs WAV to AAC directly
                combine_cmd = ["ffmpeg", "-y", "-i", demucs_vocal_wav_path, "-c:a", "libfdk_aac", "-b:a", "192k", combined_vocals_aac_path]
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}") # Keep command execution line uncolored
                subprocess.run(combine_cmd, check=True)
                print(f"{Fore.GREEN}Demucs vocals re-encoded to AAC successfully.{Style.RESET_ALL}")
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}Error re-encoding Demucs vocals: {e}{Style.RESET_ALL}")
                return False
        elif not demucs_input_exists:
            print(f"{Fore.YELLOW}Only Spleeter vocals found. Using Spleeter vocals directly for the combined track.{Style.RESET_ALL}")
            try:
                # Re-encode Spleeter WAV to AAC directly
                combine_cmd = ["ffmpeg", "-y", "-i", spleeter_vocal_wav_path, "-c:a", "libfdk_aac", "-b:a", "192k", combined_vocals_aac_path]
                print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}") # Keep command execution line uncolored
                subprocess.run(combine_cmd, check=True)
                print(f"{Fore.GREEN}\N{check mark} Spleeter vocals re-encoded to AAC successfully.{Style.RESET_ALL}")
            except subprocess.CalledProcessError as e:
                print(f"{Fore.RED}\N{CROSS MARK}' Error re-encoding Spleeter vocals: {e}{Style.RESET_ALL}")
                return False
        else:
            # Both exist, align them first
            aligned_spleeter, aligned_demucs = align_audio_tracks(spleeter_vocal_wav_path, demucs_vocal_wav_path, aligned_spleeter_vocals_path, aligned_demucs_vocals_path)

            if aligned_spleeter and aligned_demucs:
                try:
                    combine_cmd = [
                        "ffmpeg",
                        "-loglevel", "error",
                        "-y",
                        "-i", aligned_spleeter,  # Input 0 (aligned Spleeter)
                        "-i", aligned_demucs,    # Input 1 (aligned Demucs)
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[a]", # Mix two audio streams
                        #"-filter_complex",
                        #"[1:a]pan=mono|c0=c0[demucs_m];"  # Extract mono from Demucs
                        #"[0:a]pan=mono|c0=c0[spleeter_m];"  # Extract mono from Spleeter
                        #"[demucs_m][spleeter_m]amerge=inputs=2[a]",  # Merge to stereo: Demucs left, Spleeter right
                        "-map", "[a]",
                        "-c:a", "libfdk_aac",
                        "-b:a", "192k",
                        combined_vocals_aac_path
                    ]
                    print(f"\n{Fore.MAGENTA}Executing: {' '.join(combine_cmd)}") # Keep command execution line uncolored
                    subprocess.run(combine_cmd, check=True)
                    print(f"\n{Fore.GREEN}\N{check mark} Vocals combined successfully.{Style.RESET_ALL}")
                except subprocess.CalledProcessError as e:
                    print(f"{Fore.RED}\N{CROSS MARK}' Error combining AAC files: {e}{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}Error: Alignment failed. Cannot combine vocal tracks.{Style.RESET_ALL}")
                return False


        # 5. Create new video file with original video and new combined audio
        output_video = f"nomusic-{os.path.basename(input_file)}"
        
        print(f"\n{Fore.CYAN}5. Creating final video: {output_video}...{Style.RESET_ALL}")
        try:
            final_ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-y", # Overwrite output files without asking
                "-i", input_file, # Input video (original)
                "-i", combined_vocals_aac_path, # Input audio (combined vocals)
                "-c:v", "copy", # Copy video stream without re-encoding
                "-c:a", "libfdk_aac", # Encode audio to AAC
                "-map", "0:v:0", # Map video stream from first input
                "-map", "1:a:0", # Map audio stream from second input
                "-shortest", # Finish when the shortest input stream ends (usually video)
                output_video
            ]
            print(f"\n{Fore.MAGENTA}Executing: {' '.join(final_ffmpeg_cmd)}") # Keep command execution line uncolored
            subprocess.run(final_ffmpeg_cmd, check=True)
            print(f"\n{Fore.GREEN}\N{check mark} Successfully created {output_video}{Style.RESET_ALL}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}\N{cross mark}Error creating new video: {e}{Style.RESET_ALL}")
            return False

    finally:
        # Apply cyan color for headers
        print(f"\n{Fore.CYAN}--- Cleanup of temporary files ---{Style.RESET_ALL}")
        # Clean up files created with tempfile.NamedTemporaryFile
        for f_path in [temp_audio_wav_path, combined_vocals_aac_path, 
                       aligned_spleeter_vocals_path, aligned_demucs_vocals_path]:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    # Apply blue color for temporary file actions
                    print(f"{Fore.BLUE}Removed temporary file: {f_path}{Style.RESET_ALL}")
                except OSError as e:
                    print(f"{Fore.RED}Error removing temporary file {f_path}: {e}{Style.RESET_ALL}")

        # Clean up the temporary directory for Spleeter segments if it was created
        if temp_spleeter_segments_dir and os.path.exists(temp_spleeter_segments_dir):
            try:
                shutil.rmtree(temp_spleeter_segments_dir)
                print(f"{Fore.BLUE}Removed temporary directory: {temp_spleeter_segments_dir}{Style.RESET_ALL}")
            except OSError as e:
                print(f"{Fore.RED}Error removing temporary directory {temp_spleeter_segments_dir}: {e}{Style.RESET_ALL}")

        # Clean up spleeter_out and demucs_out directories
        for dir_path in [spleeter_out_path, demucs_base_out_path]:
            if os.path.exists(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    print(f"{Fore.BLUE}Removed output directory: {dir_path}{Style.RESET_ALL}")
                except OSError as e:
                    print(f"{Fore.RED}Error removing output directory {dir_path}: {e}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}--- Processing complete ---{Style.RESET_ALL}")


if __name__ == "__main__":
    # Initialize Colorama for cross-platform compatibility (especially Windows)
    init()
    try:
        input_video_file = "patrol.mp4"  # Replace with your input file

        success = process_video(input_video_file)
        if success:
            # Apply green color for script success
            print(f"\n{Fore.GREEN}Script finished successfully for {input_video_file}.{Style.RESET_ALL}")
        else:
            # Apply red color for script failure
            print(f"\n{Fore.RED}Script failed for {input_video_file}. Check logs above.{Style.RESET_ALL}")
    finally:
        # Deinitialize Colorama to reset terminal colors
        deinit()