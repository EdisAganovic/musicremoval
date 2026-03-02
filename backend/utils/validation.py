"""
Path sanitization and URL validation.
"""
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