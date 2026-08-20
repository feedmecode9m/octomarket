"""Replay speed and status helpers."""

from typing import Union

VALID_SPEEDS = ("1x", "2x", "4x")
SPEED_MULTIPLIERS = {"1x": 1, "2x": 2, "4x": 4}

REPLAY_STATUSES = ("idle", "running", "paused", "completed")


def normalize_speed(speed: Union[str, int, float]) -> str:
    """Normalize speed to 1x, 2x, or 4x."""
    if isinstance(speed, str) and speed in VALID_SPEEDS:
        return speed
    try:
        val = int(float(speed))
    except (TypeError, ValueError):
        return "1x"
    if val >= 4:
        return "4x"
    if val >= 2:
        return "2x"
    return "1x"


def map_session_state(session_state: str, at_end: bool) -> str:
    """Map market session state to replay status."""
    if at_end or session_state == "closed":
        return "completed"
    if session_state == "paused":
        return "paused"
    if session_state in ("open", "pre_market"):
        return "running"
    return "idle"
