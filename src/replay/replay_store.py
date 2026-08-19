"""File-backed durable storage for replay records."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_REPLAY_DIR = Path(__file__).resolve().parents[2] / "data" / "replay"
DEFAULT_RECORDS_FILE = "records.jsonl"


class ReplayStore:
    """Persist replay records as JSON lines on disk."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else DEFAULT_REPLAY_DIR / DEFAULT_RECORDS_FILE
        self._lock = threading.RLock()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record_id = record["id"]
        with self._lock:
            self._records[record_id] = _deepcopy_record(record)
            self._persist()
        return self.get(record_id) or record

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._records.get(record_id)
            return _deepcopy_record(record) if record else None

    def get_by_plan_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for record in self._records.values():
                if record.get("plan_id") == plan_id:
                    return _deepcopy_record(record)
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(
                self._records.values(),
                key=lambda r: r.get("metadata", {}).get("created_at", ""),
                reverse=True,
            )
            return [_deepcopy_record(item) for item in items]

    def list_by_instrument(self, instrument_id: str) -> List[Dict[str, Any]]:
        key = instrument_id.upper()
        with self._lock:
            items = [
                record
                for record in self._records.values()
                if record.get("market", {}).get("instrument_id", "").upper() == key
            ]
            items.sort(key=lambda r: r.get("metadata", {}).get("created_at", ""), reverse=True)
            return [_deepcopy_record(item) for item in items]

    def reset(self, *, clear_file: bool = True) -> None:
        with self._lock:
            self._records.clear()
            if clear_file and self._path.exists():
                self._path.unlink()

    def reload(self) -> None:
        with self._lock:
            self._records.clear()
            self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("id"):
                    self._records[record["id"]] = record

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        items = sorted(
            self._records.values(),
            key=lambda r: r.get("metadata", {}).get("created_at", ""),
        )
        with tmp_path.open("w", encoding="utf-8") as handle:
            for record in items:
                handle.write(json.dumps(record, separators=(",", ":")))
                handle.write("\n")
        os.replace(tmp_path, self._path)


_store_instance: Optional[ReplayStore] = None


def get_replay_store(path: Optional[Path] = None) -> ReplayStore:
    global _store_instance
    if path is not None:
        return ReplayStore(path=path)
    if _store_instance is None:
        _store_instance = ReplayStore()
    return _store_instance


def reset_replay_store() -> None:
    global _store_instance
    if _store_instance is not None:
        _store_instance.reset(clear_file=True)
    _store_instance = None


def _deepcopy_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(record))
