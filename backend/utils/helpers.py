"""
Generic helper functions.
"""


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