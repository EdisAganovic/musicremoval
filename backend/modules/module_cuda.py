"""
MODULE: module_cuda.py - GPU/CUDA DETECTION & HARDWARE PROFILING

ROLE: Checks PyTorch CUDA availability, profiles GPU hardware, and saves NVENC specs to data/nvidia.json.
"""
import os
import json
import subprocess
from colorama import Fore, Style

NVIDIA_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "nvidia.json"))


def determine_nvenc_capabilities(gpu_name: str, vram_gb: float) -> dict:
    """
    Infers NVENC hardware capabilities, dual-engine presence, and optimal parallel chunk count.
    """
    name = (gpu_name or "").upper()

    # Cards with Dual NVENC hardware engines
    dual_nvenc_models = [
        "4070 TI", "4080", "4090", "5070 TI", "5080", "5090",
        "L40", "6000 ADA", "5000 ADA", "4500 ADA", "4000 ADA"
    ]
    # Workstation cards with Triple NVENC hardware engines
    triple_nvenc_models = [
        "RTX 6000 ADA", "L40S"
    ]

    if any(m in name for m in triple_nvenc_models):
        nvenc_count = 3
        optimal_chunks = 6
    elif any(m in name for m in dual_nvenc_models):
        nvenc_count = 2
        optimal_chunks = 4
    elif "RTX" in name or "GTX" in name or "QUADRO" in name or "TESLA" in name:
        # Standard Single NVENC Engine
        nvenc_count = 1
        optimal_chunks = 2 if vram_gb >= 6.0 else 1
    else:
        nvenc_count = 1
        optimal_chunks = 2 if vram_gb >= 6.0 else 1

    # AV1 Hardware Encode Support (Ada Lovelace 40-series & Blackwell 50-series)
    av1_support = any(gen in name for gen in ["RTX 40", "RTX 50", "ADA", "BLACKWELL", "L4", "L40"])

    return {
        "gpu_name": gpu_name,
        "vram_gb": round(vram_gb, 2),
        "nvenc_engines": nvenc_count,
        "optimal_chunks": optimal_chunks,
        "max_concurrent_sessions": 5,
        "supports_av1_nvenc": av1_support,
        "supports_hevc_nvenc": True,
        "supports_h264_nvenc": True,
        "recommended_preset": "p4",
        "recommended_tune": "hq"
    }


def detect_and_save_nvidia_info() -> dict:
    """
    Detects active NVIDIA GPU details and writes them to data/nvidia.json.
    """
    info = {
        "cuda_available": False,
        "gpu_name": "Unknown",
        "vram_gb": 0.0,
        "cuda_version": None,
        "nvenc_engines": 1,
        "optimal_chunks": 2,
        "max_concurrent_sessions": 5,
        "supports_av1_nvenc": False,
        "supports_hevc_nvenc": False,
        "supports_h264_nvenc": False,
        "recommended_preset": "p4",
        "recommended_tune": "hq"
    }

    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            gpu_name = props.name
            vram_gb = props.total_memory / (1024 ** 3)
            caps = determine_nvenc_capabilities(gpu_name, vram_gb)

            info.update(caps)
            info["cuda_available"] = True
            info["cuda_version"] = str(torch.version.cuda)
            info["device_count"] = torch.cuda.device_count()
            info["compute_capability"] = f"{props.major}.{props.minor}"
    except Exception:
        # Fallback to nvidia-smi if torch not loaded
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=gpu_name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, check=True
            )
            lines = res.stdout.strip().splitlines()
            if lines:
                parts = lines[0].split(",")
                gpu_name = parts[0].strip()
                vram_gb = float(parts[1].strip()) / 1024.0
                caps = determine_nvenc_capabilities(gpu_name, vram_gb)
                info.update(caps)
                info["cuda_available"] = True
        except Exception:
            pass

    try:
        os.makedirs(os.path.dirname(NVIDIA_CONFIG_PATH), exist_ok=True)
        with open(NVIDIA_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not save nvidia.json: {e}{Style.RESET_ALL}")

    return info


def get_nvidia_config() -> dict:
    """
    Reads cached nvidia.json or detects on the fly if missing.
    """
    if os.path.exists(NVIDIA_CONFIG_PATH):
        try:
            with open(NVIDIA_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return detect_and_save_nvidia_info()


def get_optimal_nvenc_chunks(default: int = 4) -> int:
    """
    Returns the recommended parallel chunk count for the active NVIDIA GPU.
    """
    cfg = get_nvidia_config()
    return cfg.get("optimal_chunks", default)


def check_gpu_cuda_support():
    """
    Checks for PyTorch CUDA availability and prints GPU information.
    Returns True if CUDA is available, False otherwise.
    """
    print(f"\n{Fore.CYAN}2. Provjera GPU/CUDA podrške{Style.RESET_ALL}")
    try:
        info = detect_and_save_nvidia_info()
        if info.get("cuda_available"):
            print(f"{Fore.GREEN}CUDA Version: {info.get('cuda_version', 'N/A')} # {info.get('gpu_name')} ({info.get('vram_gb')} GB VRAM, {info.get('nvenc_engines')}x NVENC engines -> {info.get('optimal_chunks')} parallel chunks){Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}PyTorch CUDA is NOT AVAILABLE.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}  - Check if NVIDIA drivers are installed.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}  - Check if CUDA Toolkit is installed and its paths are configured correctly.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}  - Remove pip uninstall torch torchaudio torchvision and install again with CUDA support from PyTorch website.{Style.RESET_ALL}")
            print(f"{Fore.RED}Demucs and Spleeter will run on CPU, which can be significantly slower.{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"{Fore.RED}An error occurred while checking for CUDA support: {e}{Style.RESET_ALL}")
        return False

