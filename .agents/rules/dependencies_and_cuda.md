# Python Dependencies & CUDA Rules

1. **PyTorch CUDA Repository Locking**:
   - Always preserve the PyTorch CUDA index and sources in `pyproject.toml`:
     ```toml
     [[tool.uv.index]]
     name = "pytorch-cu128"
     url = "https://download.pytorch.org/whl/cu128"
     explicit = true

     [tool.uv.sources]
     torch = { index = "pytorch-cu128" }
     torchaudio = { index = "pytorch-cu128" }
     torchvision = { index = "pytorch-cu128" }
     ```
   - Never replace with vanilla PyPI `torch` packages or remove the cu128 source configuration, as `uv run` will downgrade to CPU.

2. **Websockets & Uvicorn Compatibility**:
   - `uvicorn` requires `websockets<14.0.0` (specifically `websockets 13.x` or lower) due to legacy handshake protocol dependencies.
   - Always keep `"websockets<14.0.0"` in `dependencies` list in `pyproject.toml`.

3. **Uvicorn Reload Scope**:
   - When running uvicorn in dev mode / batch scripts, always restrict reload watching to `--reload-dir backend` to prevent watching `.venv` or temporary yt-dlp files.

4. **Video Resolution Preservation**:
   - Never hardcode fixed scale dimensions like `scale=1920:1080` in FFmpeg video encoding pipelines unless explicitly requested as a preset. Always preserve original aspect ratio and resolution using `-pix_fmt yuv420p`.
