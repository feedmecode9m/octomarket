"""Step through historical OHLCV candles one at a time."""

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class Candle:
    """Single OHLCV candle."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    index: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "index": self.index,
        }


class MarketReplayEngine:
    """Load historical data and replay candles with play/pause/speed controls."""

    VALID_SPEEDS = (1, 2, 4)

    def __init__(self):
        self._lock = threading.RLock()
        self._data = pd.DataFrame()
        self._index = -1
        self._symbol = ""
        self._is_playing = False
        self._speed = 1
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_step_callbacks: List = []

    def load(self, data: pd.DataFrame, symbol: str = "") -> int:
        """Load OHLCV data. Returns number of candles."""
        with self._lock:
            if data.empty:
                self._data = pd.DataFrame()
                self._index = -1
                self._symbol = symbol
                return 0

            required = {"Open", "High", "Low", "Close", "Volume"}
            if not required.issubset(set(data.columns)):
                raise ValueError(f"Data must contain columns: {required}")

            self._data = data.copy()
            self._index = -1
            self._symbol = symbol.upper()
            self.pause()
            return len(self._data)

    def step(self) -> Optional[Candle]:
        """Advance one candle. Returns the new candle or None if at end."""
        with self._lock:
            if self._data.empty:
                return None

            next_index = self._index + 1
            if next_index >= len(self._data):
                self._is_playing = False
                return None

            self._index = next_index
            return self._candle_at(self._index)

    def step_back(self) -> Optional[Candle]:
        """Go back one candle."""
        with self._lock:
            if self._data.empty or self._index <= 0:
                return None
            self._index -= 1
            return self._candle_at(self._index)

    def reset(self):
        """Reset to before the first candle."""
        with self._lock:
            self._index = -1
            self.pause()

    def seek(self, index: int) -> Optional[Candle]:
        """Jump to a specific candle index."""
        with self._lock:
            if self._data.empty:
                return None
            index = max(-1, min(index, len(self._data) - 1))
            self._index = index
            if index < 0:
                return None
            return self._candle_at(index)

    def get_current_candle(self) -> Optional[Candle]:
        with self._lock:
            if self._index < 0 or self._data.empty:
                return None
            return self._candle_at(self._index)

    def play(self, step_callback=None):
        """Start auto-stepping in a background thread."""
        with self._lock:
            if self._data.empty or self._is_playing:
                return
            self._is_playing = True
            self._stop_event.clear()
            if step_callback:
                self._on_step_callbacks = [step_callback]
            self._thread = threading.Thread(target=self._play_loop, daemon=True)
            self._thread.start()

    def pause(self):
        with self._lock:
            self._is_playing = False
            self._stop_event.set()

    def set_speed(self, speed: int) -> int:
        """Set replay speed multiplier (1, 2, or 4)."""
        with self._lock:
            if speed not in self.VALID_SPEEDS:
                speed = min(self.VALID_SPEEDS, key=lambda s: abs(s - speed))
            self._speed = speed
            return self._speed

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._data)
            current = self.get_current_candle()
            return {
                "symbol": self._symbol,
                "total_candles": total,
                "current_index": self._index,
                "progress_pct": round((self._index + 1) / total * 100, 1) if total > 0 else 0,
                "is_playing": self._is_playing,
                "speed": self._speed,
                "at_end": self._index >= total - 1 if total > 0 else False,
                "current_candle": current.to_dict() if current else None,
            }

    def get_visible_data(self) -> pd.DataFrame:
        """Return data up to and including current candle (for charting)."""
        with self._lock:
            if self._data.empty or self._index < 0:
                return pd.DataFrame()
            return self._data.iloc[: self._index + 1].copy()

    def _play_loop(self):
        base_delay = 1.0
        while True:
            with self._lock:
                if not self._is_playing:
                    break
                speed = self._speed

            candle = self.step()
            if candle is None:
                break

            for cb in self._on_step_callbacks:
                try:
                    cb(candle)
                except Exception:
                    pass

            delay = base_delay / speed
            if self._stop_event.wait(timeout=delay):
                break

        with self._lock:
            self._is_playing = False

    def _candle_at(self, index: int) -> Candle:
        row = self._data.iloc[index]
        ts = self._data.index[index]
        timestamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        return Candle(
            timestamp=timestamp,
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
            index=index,
        )


_replay_instance: Optional[MarketReplayEngine] = None


def get_replay_engine() -> MarketReplayEngine:
    global _replay_instance
    if _replay_instance is None:
        _replay_instance = MarketReplayEngine()
    return _replay_instance
