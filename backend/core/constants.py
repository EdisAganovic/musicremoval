"""
All hardcoded paths and threshold settings.
"""
import os

# Root directories - always relative to project root, not CWD
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOAD_DIR = os.path.join(_PROJECT_ROOT, "download")
NOMUSIC_DIR = os.path.join(_PROJECT_ROOT, "nomusic")

# File paths for data persistence. Keep these anchored to the project so
# launching the backend from a different working directory cannot split state.
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
LIBRARY_FILE = os.path.join(DATA_DIR, "library.json")
QUEUE_FILE = os.path.join(DATA_DIR, "download_queue.json")
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "notifications.json")
METADATA_CACHE_FILE = os.path.join(DATA_DIR, "metadata_cache.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# Settings
MAX_LOGS = 500
MAX_NOTIFICATIONS = 50

# Separation defaults - single source of truth for every separation method.
# Referenced by models.py, services/separation_service.py, routes/separation.py
# and modules/module_processor.py so the defaults never drift apart.
DEFAULT_MODEL = "both"
DEFAULT_ROFORMER_MODEL = "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"
DEFAULT_TIGER_TARGET = "dialogue_sfx"
DEFAULT_TIGER_OVERLAP = 50
