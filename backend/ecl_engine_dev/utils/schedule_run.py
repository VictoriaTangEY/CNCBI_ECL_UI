"""
Schedule Run Module
Handles checking if today is a scheduled run day based on calendar file.
"""

from datetime import datetime, timedelta
import calendar
import sys
from pathlib import Path


def is_month_end(date):
    """Check if the given date is the last day of the month"""
    last_day = calendar.monthrange(date.year, date.month)[1]
    return date.day == last_day


def should_run_today(calendar_path="batch_calendar.txt"):
    """
    Check if today is a scheduled run day based on calendar file.

    Args:
        calendar_path (str): Path to the calendar file

    Returns:
        bool: True if today should run, False otherwise
    """
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    try:
        with open(calendar_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()
                     and not line.strip().startswith('#')]

        # Check specific dates first
        if today_str in lines:
            return True

        # Check pattern rules
        for line in lines:
            if line == "EVERY_FRIDAY" and today.weekday() == 4:  # Friday = 4
                return True
            elif line == "MONTH_END" and is_month_end(today):
                return True

        return False

    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return False


def check_and_exit_if_not_scheduled(calendar_path="batch_calendar.txt"):
    """
    Check if today is a scheduled run day and exit if not.

    Args:
        calendar_path (str): Path to the calendar file
    """
    if not should_run_today(calendar_path):
        print("Today is not a scheduled run day. Exiting.")
        sys.exit(0)
