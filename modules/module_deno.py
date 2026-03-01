"""
MODULE: module_deno.py - DENO RUNTIME HELPER

ROLE: Executes Deno JavaScript/TypeScript scripts from Python

KEY FUNCTIONS:
  run_deno_script(script_path, args) → dict
    - Returns: {"status": "success"|"error"|"exception", "output"|"error": str}
    - Runs: deno run -A <script_path> [args...]
    - Requires Deno installed on system
  
  deno_eval(code) → str
    - Returns: JavaScript evaluation result or error message
    - Runs: deno eval "<code>"

USE CASES:
  - Running frontend build scripts
  - Executing TypeScript utilities
  - JS/TS code evaluation from Python

DEPENDENCIES:
  - Deno runtime must be installed and in PATH
  - subprocess module for process execution

FLAGS:
  -A: Allow all permissions (network, read, write, etc.)
"""

def run_deno_script(script_path: str, args: list = None):
    """Executes a Deno script and returns the output ✨."""
    if args is None:
        args = []
    
    # Check if deno is installed
    try:
        subprocess.run(["deno", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"error": "Deno is not installed on this system."}

    command = ["deno", "run", "-A", script_path] + args
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout.strip()}
        else:
            return {"status": "error", "error": result.stderr.strip()}
    except Exception as e:
        return {"status": "exception", "error": str(e)}

def deno_eval(code: str):
    """Evaluates a snippet of JS/TS code using Deno ⚡."""
    try:
        result = subprocess.run(
            ["deno", "eval", code],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return str(e)
