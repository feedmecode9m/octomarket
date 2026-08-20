"""Shared filesystem roots — production can mount DATA_DIR=/data."""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """
    Root for JSONL persistence (replay / learning / research).

    Local default: <repo>/data
    Production: set DATA_DIR=/data (Railway volume mount).
    """
    override = os.environ.get("DATA_DIR") or os.environ.get("OCTOMARKET_DATA_DIR")
    if override:
        return Path(override)
    return _PROJECT_ROOT / "data"
