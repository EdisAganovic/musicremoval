"""
MODULE: module_cuda.py - GPU/CUDA DETECTION

ROLE: Checks for PyTorch CUDA availability and prints GPU information

KEY FUNCTIONS:
  check_gpu_cuda_support() → bool
    - Returns True if torch.cuda.is_available()
    - Prints CUDA version, GPU name, and device count
    - Provides troubleshooting hints if CUDA not found

OUTPUT:
  - Prints colored status messages (cyan/green/red/yellow)
  - GPU info: CUDA version, device name, count
  - Troubleshooting: Driver check, CUDA toolkit, PyTorch reinstall

DEPENDENCIES:
  - torch: PyTorch library for CUDA detection

NOTE:
  - Demucs and Spleeter run on CPU if CUDA unavailable (slower)
"""
import torch
from colorama import Fore, Style

def check_gpu_cuda_support():
    """
    Checks for PyTorch CUDA availability and prints GPU information.
    Returns True if CUDA is available, False otherwise.
    """
    # Apply cyan color for headers--
    print(f"\n{Fore.CYAN}2. Provjera GPU/CUDA podrške{Style.RESET_ALL}")
    try:
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
    except Exception as e:
        print(f"{Fore.RED}An error occurred while checking for CUDA support: {e}{Style.RESET_ALL}")
        return False

