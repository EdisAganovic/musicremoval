"""
CORE: gpu_pool.py - MULTI-GPU RESOURCE SCHEDULER & WORKER POOL

ROLE: Manages concurrent GPU resource allocation across PyTorch, Demucs, Roformer,
      TIGER-DnR, Spleeter, and FFmpeg NVENC processes.
"""
import os
import threading
import queue
import time
from colorama import Fore, Style
from modules.module_cuda import get_available_cuda_devices, get_nvidia_config


class GPUPoolManager:
    """
    Thread-safe resource manager for multi-GPU scheduling.
    Allows round-robin leasing and weighted allocation based on VRAM capacity.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._devices = []
        self._device_queue = queue.Queue()
        self._active_leases = {}
        self.reload_devices()

    def reload_devices(self):
        """Reloads detected CUDA devices and initializes the queue."""
        with self._lock:
            dev_list = get_available_cuda_devices()
            self._devices = dev_list if dev_list else ["cpu"]
            # Clear existing queue
            while not self._device_queue.empty():
                try:
                    self._device_queue.get_nowait()
                except queue.Empty:
                    break
            # Populate queue with available devices
            for dev in self._devices:
                self._device_queue.put(dev)
            self._active_leases = {dev: 0 for dev in self._devices}

    @property
    def device_count(self) -> int:
        return len(self._devices)

    @property
    def devices(self) -> list:
        return list(self._devices)

    def get_primary_device(self) -> str:
        """Returns the strongest/primary GPU (usually cuda:0)."""
        return self._devices[0] if self._devices else "cpu"

    def get_secondary_device(self) -> str:
        """Returns the secondary GPU (cuda:1) if present, else primary."""
        if len(self._devices) > 1:
            return self._devices[1]
        return self.get_primary_device()

    def lease_device(self, timeout: float = 30.0) -> str:
        """
        Leases an available GPU device string from the pool.
        Must be returned using release_device().
        """
        try:
            dev = self._device_queue.get(timeout=timeout)
            with self._lock:
                self._active_leases[dev] = self._active_leases.get(dev, 0) + 1
            return dev
        except queue.Empty:
            # Fallback to least loaded device
            with self._lock:
                least_loaded = min(self._active_leases, key=self._active_leases.get, default=self.get_primary_device())
                self._active_leases[least_loaded] = self._active_leases.get(least_loaded, 0) + 1
                return least_loaded

    def release_device(self, dev: str):
        """Releases a leased device back into the scheduling pool."""
        with self._lock:
            if dev in self._active_leases:
                self._active_leases[dev] = max(0, self._active_leases[dev] - 1)
        self._device_queue.put(dev)


# Global singleton instance
gpu_pool = GPUPoolManager()


class GPUDeviceLease:
    """Context manager for leasing a GPU device safely."""
    def __init__(self, target_device=None):
        self.target_device = target_device
        self.leased_device = None

    def __enter__(self):
        if self.target_device:
            self.leased_device = self.target_device
        else:
            self.leased_device = gpu_pool.lease_device()
        return self.leased_device

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.target_device and self.leased_device:
            gpu_pool.release_device(self.leased_device)
