"""Per-symbol drawing persistence for chart workspace."""

import threading
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional

from .drawings import normalize_drawing, validate_drawing_update


class DrawingStore:
    """In-memory drawing storage keyed by symbol."""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_symbol: Dict[str, List[Dict[str, Any]]] = {}

    def list_drawings(self, symbol: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            return deepcopy(self._by_symbol.get(symbol, []))

    def get_drawing(self, symbol: str, drawing_id: str) -> Optional[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            for item in self._by_symbol.get(symbol, []):
                if item.get("id") == drawing_id:
                    return deepcopy(item)
        return None

    def create_drawing(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = symbol.upper()
        entry = normalize_drawing(data)
        entry["id"] = entry.get("id") or str(uuid.uuid4())
        with self._lock:
            self._by_symbol.setdefault(symbol, []).append(deepcopy(entry))
            return deepcopy(entry)

    def update_drawing(self, symbol: str, drawing_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = symbol.upper()
        with self._lock:
            items = self._by_symbol.get(symbol, [])
            for i, item in enumerate(items):
                if item.get("id") == drawing_id:
                    merged = validate_drawing_update(item, data)
                    merged["id"] = drawing_id
                    items[i] = merged
                    return deepcopy(merged)
        raise KeyError(f"Drawing '{drawing_id}' not found for {symbol}")

    def delete_drawing(self, symbol: str, drawing_id: str) -> bool:
        symbol = symbol.upper()
        with self._lock:
            items = self._by_symbol.get(symbol, [])
            for i, item in enumerate(items):
                if item.get("id") == drawing_id:
                    items.pop(i)
                    return True
        return False

    def clear_symbol(self, symbol: str):
        symbol = symbol.upper()
        with self._lock:
            self._by_symbol.pop(symbol, None)

    def reset(self):
        with self._lock:
            self._by_symbol.clear()


_store_instance: Optional[DrawingStore] = None


def get_drawing_store() -> DrawingStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = DrawingStore()
    return _store_instance
