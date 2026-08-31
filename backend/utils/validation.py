"""
Path sanitization and URL validation.
"""
import os
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse


def safe_path(user_input: str, base_dir: str) -> Optional[str]:
    """
    Validate and sanitize file paths to prevent path traversal attacks.
    Returns resolved absolute path if valid, None otherwise.
    """
    try:
        resolved = Path(base_dir).resolve()
        target = (resolved / user_input).resolve()
        if str(target).startswith(str(resolved)):
            return str(target)
    except (ValueError, TypeError, OSError):
        pass
    return None


def is_path_within_allowed_roots(target: str, allowed_roots: list) -> bool:
    """
    Return True if `target` (an absolute path) resides inside any of the allowed
    root directories. Guards against path traversal in file-serving / file-open
    endpoints. Accepts symlink-unsafe comparisons on the normalized absolute path.
    """
    if not target:
        return False
    try:
        target_abs = os.path.abspath(os.path.normpath(target)).lower()
    except (ValueError, TypeError, OSError):
        return False
    for root in allowed_roots:
        if not root:
            continue
        try:
            root_abs = os.path.abspath(os.path.normpath(root)).lower()
        except (ValueError, TypeError, OSError):
            continue
        if target_abs == root_abs or target_abs.startswith(root_abs + os.sep) or target_abs.startswith(root_abs + "/"):
            return True
    return False


def validate_url(url: str) -> bool:
    """
    Basic URL validation.
    Returns True if URL appears valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False
    # Basic URL pattern check
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    # Check for obviously malicious patterns
    dangerous_patterns = ['javascript:', 'data:', 'file:', 'vbscript:']
    if any(pattern in url.lower() for pattern in dangerous_patterns):
        return False
    return True


def validate_youtube_url(url: str) -> bool:
    """
    Validate YouTube URL format.
    Returns True if URL appears to be a valid YouTube URL.
    """
    if not validate_url(url):
        return False
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'www.youtu.be']
    try:
        parsed = urlparse(url)
        if parsed.netloc in youtube_domains:
            return True
    except (ImportError, ValueError):
        pass
    return False


def is_youtube_url(url: str) -> bool:
    """
    Returns True if URL is from YouTube (youtube.com or youtu.be).
    Used to determine whether to apply YouTube-specific yt-dlp options.
    """
    if not url:
        return False
    try:
        url_check = url.strip()
        if not (url_check.startswith('http://') or url_check.startswith('https://')):
            url_check = 'https://' + url_check
        parsed = urlparse(url_check)
        netloc = parsed.netloc.lower()
        return netloc == 'youtu.be' or netloc.endswith('youtu.be') or netloc.endswith('youtube.com')
    except Exception:
        return False


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename by removing or replacing invalid characters.
    
    Args:
        filename: The original filename to sanitize
        max_length: Maximum length for the filename (default 255)
    
    Returns:
        Sanitized filename that's safe for the filesystem.
    """
    if not filename or not isinstance(filename, str):
        return "unnamed"
    
    # SECURITY: Remove path traversal attempts
    filename = filename.replace('..', '_')
    
    # SECURITY: Only keep the basename (prevent directory traversal)
    filename = os.path.basename(filename)
    
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Remove leading/trailing spaces and dots which are invalid on Windows
    filename = filename.strip(' .')
    
    # Limit length while preserving extension
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        name = name[:max_name_length]
        filename = name + ext
    
    return filename