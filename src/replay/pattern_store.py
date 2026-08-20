"""Lightweight JSONL index over completed ReplayRecords."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.paths import get_data_dir

DEFAULT_PATTERNS_FILE = "patterns.jsonl"


class PatternStore:
    """Store pattern indexes keyed by ReplayRecord id."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else get_data_dir() / "replay" / DEFAULT_PATTERNS_FILE
        self._lock = threading.RLock()
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def upsert(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        record_id = pattern["record_id"]
        with self._lock:
            self._patterns[record_id] = _deepcopy(pattern)
            self._persist()
        return self.get(record_id) or pattern

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._patterns.get(record_id)
            return _deepcopy(item) if item else None

    def get_by_plan_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for pattern in self._patterns.values():
                if pattern.get("plan_id") == plan_id:
                    return _deepcopy(pattern)
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(
                self._patterns.values(),
                key=lambda p: p.get("indexed_at", ""),
                reverse=True,
            )
            return [_deepcopy(item) for item in items]

    def list_closed(self) -> List[Dict[str, Any]]:
        return [p for p in self.list_all() if p.get("status") == "closed"]

    def reset(self, *, clear_file: bool = True) -> None:
        with self._lock:
            self._patterns.clear()
            if clear_file and self._path.exists():
                self._path.unlink()

    def reload(self) -> None:
        with self._lock:
            self._patterns.clear()
            self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                pattern = json.loads(line)
                if pattern.get("record_id"):
                    self._patterns[pattern["record_id"]] = pattern

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        items = sorted(
            self._patterns.values(),
            key=lambda p: p.get("indexed_at", ""),
        )
        with tmp_path.open("w", encoding="utf-8") as handle:
            for pattern in items:
                handle.write(json.dumps(pattern, separators=(",", ":")))
                handle.write("\n")
        os.replace(tmp_path, self._path)


_store_instance: Optional[PatternStore] = None


def get_pattern_store(path: Optional[Path] = None) -> PatternStore:
    global _store_instance
    if path is not None:
        return PatternStore(path=path)
    if _store_instance is None:
        _store_instance = PatternStore()
    return _store_instance


def reset_pattern_store() -> None:
    global _store_instance
    if _store_instance is not None:
        _store_instance.reset(clear_file=True)
    _store_instance = None


def _deepcopy(item: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(item))
