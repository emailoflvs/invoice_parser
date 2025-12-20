"""
Utilities for datetime formatting.
All datetime formatting should use these functions for consistency.
"""
from datetime import datetime
from typing import Optional


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime to string without microseconds.
    Format: "2025-12-11 23:17"

    Args:
        dt: Datetime object or None

    Returns:
        Formatted string or None
    """
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M")


def format_datetime_for_db(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Prepare datetime for database storage (remove microseconds).

    Args:
        dt: Datetime object or None

    Returns:
        Datetime without microseconds or None
    """
    if dt is None:
        return None
    return dt.replace(microsecond=0)


def now() -> datetime:
    """
    Get current datetime without microseconds.

    Returns:
        Current datetime without microseconds
    """
    return datetime.now().replace(microsecond=0)


def utcnow() -> datetime:
    """
    Get current UTC datetime without microseconds.

    Returns:
        Current UTC datetime without microseconds
    """
    return datetime.utcnow().replace(microsecond=0)













