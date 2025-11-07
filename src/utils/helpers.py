"""Helper utilities."""

from typing import List


def allowed_file(filename: str, allowed_extensions: List[str] = None) -> bool:
    """Check if file has allowed extension."""
    if allowed_extensions is None:
        allowed_extensions = ['txt']
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def count_lines(filename: str) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            return len(lines)
    except:
        return 0

