import os


def format_duration(seconds) -> str:
    """
    Format duration in seconds to human readable string.
    
    Args:
        seconds: Duration in seconds (int, float, or None)
    
    Returns:
        Formatted string like "5:30" or "1:23:45" or "N/A" for invalid input
    """
    if not seconds:
        return "N/A"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    hours = minutes // 60
    if hours > 0:
        return f"{hours}:{minutes % 60:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_unique_filepath(directory: str, base_name: str, ext: str = "") -> str:
    """
    Returns a unique filepath by appending _0, _1, _2... if a file already exists in directory.
    Example:
      If 'song.mp3' exists -> 'song_0.mp3', 'song_1.mp3', etc.
    """
    if ext and not ext.startswith('.'):
        ext = f".{ext}"
    
    candidate = os.path.join(directory, f"{base_name}{ext}")
    if not os.path.exists(candidate):
        return candidate
    
    index = 0
    while True:
        candidate = os.path.join(directory, f"{base_name}_{index}{ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def get_unique_basename(directory: str, base_name: str, suffixes_to_check: list = None, ext: str = "") -> str:
    """
    Returns a unique base_name string for multi-stem or multi-file outputs.
    Checks if any file matching base_name + suffix + ext exists.
    Example:
      If 'nomusic_song_vocals.mp3' exists -> returns 'nomusic_song_0'
    """
    if suffixes_to_check is None:
        suffixes_to_check = ["_vocals", "_instrumental", "_novocals", ""]
    
    if ext and not ext.startswith('.'):
        ext = f".{ext}"
    
    # Check original base_name
    conflict = False
    for s in suffixes_to_check:
        p = os.path.join(directory, f"{base_name}{s}{ext}")
        if os.path.exists(p):
            conflict = True
            break
        # Also check without ext
        if not ext:
            for existing in os.listdir(directory) if os.path.exists(directory) else []:
                if existing.startswith(f"{base_name}{s}"):
                    conflict = True
                    break
    
    if not conflict:
        return base_name
    
    index = 0
    while True:
        candidate_base = f"{base_name}_{index}"
        conflict = False
        for s in suffixes_to_check:
            p = os.path.join(directory, f"{candidate_base}{s}{ext}")
            if os.path.exists(p):
                conflict = True
                break
            if not ext:
                for existing in os.listdir(directory) if os.path.exists(directory) else []:
                    if existing.startswith(f"{candidate_base}{s}"):
                        conflict = True
                        break
        if not conflict:
            return candidate_base
        index += 1