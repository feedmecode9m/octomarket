"""Persistent store for LearningJournalEntry artifacts."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_JOURNAL_DIR = Path(__file__).resolve().parents[2] / "data" / "learning"
DEFAULT_JOURNAL_FILE = "journal.jsonl"


class LearningJournalStore:
    """Append/lookup learning journal entries as JSON lines."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else DEFAULT_JOURNAL_DIR / DEFAULT_JOURNAL_FILE
        self._lock = threading.RLock()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._by_record: Dict[str, str] = {}
        self._load()

    def save(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        entry_id = entry.get("id")
        record_id = entry.get("record_id")
        if not entry_id:
            raise ValueError("Learning entry must include id")
        if not record_id:
            raise ValueError("Learning entry must include record_id")
        with self._lock:
            existing_id = self._by_record.get(record_id)
            if existing_id and existing_id != entry_id:
                # One journal entry per ReplayRecord — update in place
                old = self._entries.pop(existing_id, None)
                if old:
                    entry = {**entry, "id": existing_id}
                    entry_id = existing_id
            self._entries[entry_id] = json.loads(json.dumps(entry))
            self._by_record[record_id] = entry_id
            self._persist()
        return self.get(entry_id) or entry

    def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._entries.get(entry_id)
            return json.loads(json.dumps(item)) if item else None

    def get_by_record_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry_id = self._by_record.get(record_id)
            if not entry_id:
                return None
            item = self._entries.get(entry_id)
            return json.loads(json.dumps(item)) if item else None

    def list_all(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(
                self._entries.values(),
                key=lambda e: e.get("generated_at", ""),
                reverse=True,
            )
            if limit is not None:
                items = items[: max(0, limit)]
            return [json.loads(json.dumps(i)) for i in items]

    def list_for_instrument(self, instrument_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        key = instrument_id.upper()
        items = [
            e for e in self.list_all()
            if (e.get("instrument_id") or "").upper() == key
            or (e.get("continuous_id") or "").upper() == key
        ]
        return items[: max(0, limit)]

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
            self._by_record.clear()
            if self._path.exists():
                self._path.unlink()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                eid = entry.get("id")
                rid = entry.get("record_id")
                if eid:
                    self._entries[eid] = entry
                if eid and rid:
                    self._by_record[rid] = eid

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        items = sorted(self._entries.values(), key=lambda e: e.get("generated_at", ""))
        with tmp.open("w", encoding="utf-8") as handle:
            for entry in items:
                handle.write(json.dumps(entry, separators=(",", ":")))
                handle.write("\n")
        os.replace(tmp, self._path)


_store_instance: Optional[LearningJournalStore] = None


def get_learning_journal_store(path: Optional[Path] = None) -> LearningJournalStore:
    global _store_instance
    if path is not None:
        return LearningJournalStore(path=path)
    if _store_instance is None:
        _store_instance = LearningJournalStore()
    return _store_instance


def reset_learning_journal_store() -> None:
    global _store_instance
    if _store_instance is not None:
        _store_instance.reset()
    _store_instance = None
