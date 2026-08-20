"""Replay session orchestration — instrument-aware controlled time without future leakage.

Architecture (LIVE vs REPLAY):

Shared across modes:
  instrument model, chart pipeline, trade plans, execution sim, ReplayRecord lifecycle

Mode-specific (not collapsed into one state machine):
  LIVE PAPER — CandleEngine → MarketDataProvider (full history, no time index)
  REPLAY     — ReplaySessionManager → MarketSession (step index, hidden futures)

ReplaySessionManager owns replay *mode* and orchestration.
MarketSession owns replay *time index* only (internal, not a user-facing LIVE mode).
"""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from ..charting.candle_engine import get_candle_engine
from ..charting.chart_state import get_chart_state
from ..market.asset_class import AssetClass
from ..market.continuous_contract import continuous_id_for
from ..market.instrument import resolve_instrument
from ..simulation.session import MarketSession, get_market_session
from .candle_stream import (
    count_hidden_candles,
    get_start_timestamp,
    serialize_candles,
    validate_visible_index,
)
from .replay_clock import map_session_state, normalize_speed
from .replay_metrics import ReplayMetrics

MODE_LIVE_PAPER = "live_paper"
MODE_REPLAY = "replay"


def normalize_operating_mode(mode: Optional[str]) -> str:
    """Normalize API/user mode strings to canonical operating modes."""
    text = (mode or MODE_LIVE_PAPER).lower()
    if text in ("live", "live_paper"):
        return MODE_LIVE_PAPER
    if text == MODE_REPLAY:
        return MODE_REPLAY
    raise ValueError("mode must be 'live_paper' or 'replay'")


class ReplaySessionManager:
    """Canonical replay engine backed by MarketSession candle caps."""

    def __init__(self, session: Optional[MarketSession] = None):
        self._lock = threading.RLock()
        self._session_override = session
        self._instrument_id: Optional[str] = None
        self._symbol: Optional[str] = None
        self._interval = "1d"
        self._period = "1mo"
        self._speed = "1x"
        self._status = "idle"
        self._mode = MODE_LIVE_PAPER
        self._metrics = ReplayMetrics()
        self._started_at: Optional[str] = None
        self._source_record_id: Optional[str] = None

    @property
    def _session(self) -> MarketSession:
        """Resolve the active market session — never cache the singleton across research isolation."""
        return self._session_override if self._session_override is not None else get_market_session()

    def start(
        self,
        instrument_id: Optional[str] = None,
        symbol: Optional[str] = None,
        period: str = "1mo",
        interval: str = "1d",
        initial_cash: float = 10000.0,
        reset_portfolio: bool = True,
        source_record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = instrument_id or symbol
        if not raw:
            raise ValueError("instrument_id or symbol is required")

        instrument = resolve_instrument(raw)
        session_key = instrument.symbol.upper()

        with self._lock:
            if reset_portfolio:
                from ..simulation.paper_portfolio import get_paper_portfolio
                from ..trading.order_engine import get_order_engine
                from ..ai_agent.trade_journal import get_trade_journal

                get_paper_portfolio().reset(initial_cash)
                get_order_engine().clear()
                get_trade_journal().clear()

            self._session.start(
                [instrument.instrument_id],
                initial_cash=initial_cash,
                period=period,
                interval=interval,
            )
            self._instrument_id = instrument.instrument_id
            self._symbol = session_key
            self._interval = interval
            self._period = period
            self._speed = "1x"
            self._status = "running"
            self._mode = MODE_REPLAY
            self._started_at = datetime.now().isoformat()
            self._source_record_id = source_record_id
            self._metrics = ReplayMetrics()
            self._metrics.bind_symbol(session_key)

            self._sync_chart_workspace(instrument.instrument_id, interval, period)
            get_candle_engine().clear_cache()
            return self.get_state()

    def start_from_record(self, record_id: str, **kwargs) -> Dict[str, Any]:
        from .replay_store import get_replay_store

        record = get_replay_store().get(record_id)
        if not record:
            raise ValueError(f"Replay record '{record_id}' not found")

        market = record.get("market") or {}
        context = record.get("decision_context") or {}
        snapshot = context.get("market_snapshot") or {}
        chart = snapshot.get("chart") or {}

        instrument_id = market.get("instrument_id") or record.get("plan_id")
        if not instrument_id:
            raise ValueError("Replay record missing instrument identity")

        return self.start(
            instrument_id=instrument_id,
            period=kwargs.get("period") or chart.get("period") or context.get("period") or "1mo",
            interval=kwargs.get("interval") or chart.get("timeframe") or context.get("timeframe") or "1d",
            initial_cash=float(kwargs.get("initial_cash", 10000.0)),
            reset_portfolio=kwargs.get("reset_portfolio", True),
            source_record_id=record_id,
        )

    def step(self) -> Dict[str, Any]:
        with self._lock:
            state = self._session.step()
            if state.get("error"):
                return self.get_state(error=state.get("error"))

            sym = self._symbol
            candles = state.get("candles") or {}
            if sym and sym in candles:
                self._metrics.on_candle(candles[sym])

            from ..api.execution_routes import process_session_fills

            if candles:
                fills = process_session_fills(candles)
                state["fills"] = fills

            self._status = map_session_state(state.get("state", "idle"), state.get("at_end", False))
            result = self.get_state()
            result["fills"] = state.get("fills", [])
            return result

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            self._session.pause()
            self._status = "paused"
            return self.get_state()

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            self._session.resume()
            session_state = self._session.get_state()
            self._status = map_session_state(
                session_state.get("state", "idle"),
                session_state.get("at_end", False),
            )
            return self.get_state()

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            symbol = self._symbol or "AAPL"
            self._session.close()
            self._metrics = ReplayMetrics()
            self._metrics.bind_symbol(symbol)
            self._status = "idle"
            self._mode = MODE_LIVE_PAPER
            self._instrument_id = None
            self._symbol = None
            self._source_record_id = None
            get_candle_engine().clear_cache()
            return {
                "message": "Replay reset",
                "status": "idle",
                "mode": MODE_LIVE_PAPER,
                "symbol": symbol,
            }

    def set_speed(self, speed: str) -> Dict[str, Any]:
        with self._lock:
            self._speed = normalize_speed(speed)
            return self.get_state()

    def set_mode(self, mode: str) -> Dict[str, Any]:
        with self._lock:
            normalized = normalize_operating_mode(mode)
            if normalized == MODE_LIVE_PAPER and self._status in ("running", "paused"):
                self.reset()
            self._mode = normalized
            return self.get_state()

    def get_visible_candles(self, instrument_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            lookup = instrument_id or self._instrument_id or self._symbol or ""
            if not lookup or not self._session.has_symbol(lookup):
                return serialize_candles(pd.DataFrame(), -1)

            session_key = self._session.resolve_key(lookup)
            if not session_key:
                return serialize_candles(pd.DataFrame(), -1)

            df = self._session.get_ohlcv_frame(session_key)
            if df is None or df.empty:
                return serialize_candles(pd.DataFrame(), -1)

            idx = self._session.get_session_index()
            validate_visible_index(idx, len(df))
            payload = serialize_candles(df, idx)
            instrument = self._session.get_instrument(session_key) or {}
            payload["symbol"] = instrument.get("symbol") or session_key
            payload["instrument_id"] = instrument.get("instrument_id") or self._instrument_id
            payload["hidden_count"] = count_hidden_candles(len(df), idx)
            return payload

    def get_state(self, error: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            session_state = self._session.get_state()
            sym = self._symbol or (session_state.get("symbols") or [None])[0]
            total = (session_state.get("max_index") or -1) + 1
            current = session_state.get("current_index", -1)
            start_ts = None
            if sym and self._session.has_symbol(sym):
                df = self._session.get_ohlcv_frame(sym)
                start_ts = get_start_timestamp(df) if df is not None else None

            status = self._status
            if self._status == "idle":
                status = "idle"
            elif self._status == "paused":
                status = "paused"
            elif session_state.get("state") not in ("idle", "closed"):
                status = map_session_state(
                    session_state.get("state", "idle"),
                    session_state.get("at_end", False),
                )
                self._status = status

            current_candle = (session_state.get("candles") or {}).get(sym) if sym else None
            if current_candle is not None:
                current_candle = dict(current_candle)
                current_candle["index"] = current

            payload = {
                "mode": self._mode,
                "instrument": self._instrument_payload(sym),
                "instrument_id": self._instrument_id,
                "symbol": sym,
                "timeframe": self._interval,
                "period": self._period,
                "start": start_ts,
                "current_index": current,
                "total_candles": total,
                "speed": self._speed,
                "status": status,
                "progress_pct": session_state.get("progress_pct", 0),
                "hidden_candles": count_hidden_candles(total, current),
                "prices": session_state.get("prices", {}),
                "current_candle": current_candle,
                "metrics": self._metrics.to_dict(),
                "started_at": self._started_at,
                "source_record_id": self._source_record_id,
            }
            if error:
                payload["error"] = error
            return deepcopy(payload)

    def serialize(self) -> Dict[str, Any]:
        return self.get_state()

    def is_active(self) -> bool:
        with self._lock:
            return self._mode == MODE_REPLAY and self._status in ("running", "paused")

    def is_replay_mode(self) -> bool:
        with self._lock:
            return self._mode == MODE_REPLAY and self._status != "idle"

    def _instrument_payload(self, session_key: Optional[str]) -> Optional[Dict[str, Any]]:
        if not session_key:
            return None
        data = self._session.get_instrument(session_key)
        if data:
            return data
        if not self._instrument_id:
            return None
        instrument = resolve_instrument(self._instrument_id)
        payload = instrument.to_dict()
        if instrument.asset_class == AssetClass.FUTURES:
            payload["continuous_id"] = instrument.continuous_id or continuous_id_for(instrument.instrument_id)
        return payload

    def _sync_chart_workspace(self, instrument_id: str, interval: str, period: str) -> None:
        get_chart_state().update(
            instrument_id=instrument_id,
            timeframe=interval,
            period=period,
        )


_manager_instance: Optional[ReplaySessionManager] = None


def get_replay_session() -> ReplaySessionManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ReplaySessionManager()
    return _manager_instance


def is_replay_mode() -> bool:
    return get_replay_session().is_replay_mode()
