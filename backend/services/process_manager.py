"""
PROCESS MANAGER - Tracks and cleans up child processes.

Prevents zombie python.exe / ffmpeg.exe / demucs processes when the app
exits prematurely (Ctrl+C, window close, crash, etc.).

USAGE:
    from services.process_manager import tracked_run, cleanup_all_children

    # Instead of subprocess.run(cmd), use:
    result = tracked_run(cmd, ...)

    # On shutdown:
    cleanup_all_children()
"""
import os
import sys
import signal
import subprocess
import threading
import time
from typing import Optional, List
from colorama import Fore, Style


# Global set of active child processes (thread-safe)
_active_processes: dict[int, subprocess.Popen] = {}
_lock = threading.Lock()
_shutdown_initiated = False
_SPAWN_EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "SpawnWithJob.exe")
_USE_JOB_OBJECTS = sys.platform == "win32" and os.path.exists(_SPAWN_EXE)


def _log_fail(message: str):
    """Log failures into log.txt in the project root."""
    try:
        # backend/services/process_manager.py -> backend/services -> backend -> root
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_path = os.path.join(root_dir, "log.txt")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [ProcessManager] {message}\n")
    except Exception as e:
        # Fallback to stderr if logging fails
        print(f"Failed to write to log.txt: {e}", file=sys.stderr)


def tracked_run(cmd, **kwargs):
    """
    Drop-in replacement for subprocess.run() that tracks the child process.
    On app shutdown, any still-running tracked processes will be terminated.
    On Windows, it uses SpawnWithJob.exe to ensure process tree cleanup even on crash.
    
    Args:
        cmd: Command to run (list or string)
        **kwargs: All kwargs supported by subprocess.run()
        
    Returns:
        subprocess.CompletedProcess (same as subprocess.run)
    """
    global _shutdown_initiated
    if _shutdown_initiated:
        raise RuntimeError("Cannot start new processes during shutdown")

    original_cmd = cmd
    # Use SpawnWithJob.exe if available on Windows to prevent zombies
    if _USE_JOB_OBJECTS:
        if isinstance(cmd, list):
            cmd = [_SPAWN_EXE] + list(cmd)
        elif isinstance(cmd, str):
            cmd = f'"{_SPAWN_EXE}" {cmd}'

    # We need to use Popen to track the PID, then wait for completion
    # Extract timeout from kwargs since Popen doesn't support it directly
    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)

    # Handle capture_output shorthand
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    proc = subprocess.Popen(cmd, **kwargs)

    with _lock:
        _active_processes[proc.pid] = proc

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _log_fail(f"Timeout ({timeout}s) for command: {original_cmd}")
        _kill_process(proc)
        stdout, stderr = proc.communicate()
        with _lock:
            _active_processes.pop(proc.pid, None)
        raise subprocess.TimeoutExpired(original_cmd, timeout, output=stdout, stderr=stderr)
    except Exception as e:
        _log_fail(f"Exception while running command {original_cmd}: {e}")
        _kill_process(proc)
        with _lock:
            _active_processes.pop(proc.pid, None)
        raise

    with _lock:
        _active_processes.pop(proc.pid, None)

    result = subprocess.CompletedProcess(
        args=original_cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )

    if check and proc.returncode != 0:
        _log_fail(f"Process failed with exit code {proc.returncode}: {original_cmd}\nStderr: {stderr.decode() if isinstance(stderr, bytes) else stderr}")
        raise subprocess.CalledProcessError(
            proc.returncode, original_cmd, output=stdout, stderr=stderr
        )

    return result


def _kill_process(proc: subprocess.Popen):
    """Forcefully kill a process and all its children."""
    try:
        if proc.poll() is None:  # Still running
            if sys.platform == "win32":
                # On Windows, use taskkill to kill the entire process tree
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=10,
                )
            else:
                # On Unix, kill the process group
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
                time.sleep(0.5)
                if proc.poll() is None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not kill process {proc.pid}: {e}{Style.RESET_ALL}")


def get_active_processes() -> List[dict]:
    """Get info about all currently tracked active processes."""
    with _lock:
        result = []
        for pid, proc in list(_active_processes.items()):
            if proc.poll() is None:
                result.append({
                    "pid": pid,
                    "args": proc.args if hasattr(proc, "args") else "unknown",
                    "running": True,
                })
            else:
                # Already finished, clean up
                _active_processes.pop(pid, None)
        return result


def cleanup_all_children(reason: str = "shutdown"):
    """
    Kill all tracked child processes. Called on app shutdown.
    Also performs a sweep for any orphaned python/ffmpeg/demucs processes
    that belong to this working directory.
    """
    global _shutdown_initiated
    _shutdown_initiated = True

    with _lock:
        active = list(_active_processes.items())

    if active:
        print(f"\n{Fore.YELLOW}[Process Manager] Cleaning up {len(active)} child process(es) ({reason})...{Style.RESET_ALL}")
        for pid, proc in active:
            if proc.poll() is None:
                print(f"  Killing PID {pid}: {getattr(proc, 'args', 'unknown')}")
                _kill_process(proc)

        # Give processes a moment to die
        time.sleep(1)

        # Verify they're dead
        with _lock:
            still_alive = [(pid, proc) for pid, proc in _active_processes.items() if proc.poll() is None]
            if still_alive:
                print(f"{Fore.RED}  Warning: {len(still_alive)} process(es) still alive after cleanup{Style.RESET_ALL}")
            _active_processes.clear()

    print(f"{Fore.GREEN}[Process Manager] Cleanup complete.{Style.RESET_ALL}")
    _shutdown_initiated = False


def kill_stale_processes():
    """
    Kill any leftover python.exe / demucs / ffmpeg processes from previous runs.
    Called on startup to clean up orphans from a crash.
    Uses tasklist/taskkill on Windows.
    """
    if sys.platform != "win32":
        return

    my_pid = os.getpid()
    my_parent_pid = os.getppid()
    cwd_lower = os.getcwd().lower()

    targets = ["python.exe", "ffmpeg.exe", "ffprobe.exe"]
    killed_count = 0

    for target in targets:
        try:
            # Get all matching processes with their command lines
            result = subprocess.run(
                ["wmic", "process", "where", f"Name='{target}'", "get",
                 "ProcessId,CommandLine", "/format:csv"],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace'
            )

            if result.returncode != 0:
                continue

            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or "ProcessId" in line or "Node" in line:
                    continue

                parts = line.split(",")
                if len(parts) < 3:
                    continue

                cmd_line = ",".join(parts[1:-1]).lower()
                try:
                    pid = int(parts[-1].strip())
                except ValueError:
                    continue

                # Skip our own process and parent
                if pid in (my_pid, my_parent_pid):
                    continue

                # Only kill if it's related to our project (demucs, spleeter, or our modules)
                if any(marker in cmd_line for marker in [
                    "demucs", "spleeter", "module_processor",
                    "module_demucs", "module_spleeter",
                    cwd_lower,
                ]):
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            capture_output=True, timeout=5
                        )
                        killed_count += 1
                        print(f"  {Fore.YELLOW}Killed stale {target} (PID {pid}){Style.RESET_ALL}")
                    except Exception:
                        pass

        except Exception:
            pass

    if killed_count > 0:
        print(f"{Fore.GREEN}[Process Manager] Cleaned up {killed_count} stale process(es) from previous run.{Style.RESET_ALL}")
