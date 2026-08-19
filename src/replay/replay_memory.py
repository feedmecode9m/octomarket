"""Lifecycle coordinator for durable replay memory."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, Optional

from .replay_record import (
    apply_entry_fill,
    apply_exit_fill,
    apply_order_submitted,
    build_replay_record_from_plan,
)
from .scoring_service import apply_scoring, score_replay_record
from .replay_store import ReplayStore, get_replay_store


class ReplayMemory:
    """Connect trade plan and execution lifecycle events to durable replay records."""

    def __init__(self, store: Optional[ReplayStore] = None):
        self._store = store or get_replay_store()
        self._lock = threading.RLock()
        self._by_plan: Dict[str, str] = {}
        self._by_entry_order: Dict[str, str] = {}
        self._index_loaded_records()

    def on_plan_created(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        record = build_replay_record_from_plan(plan)
        saved = self._store.save(record)
        with self._lock:
            self._by_plan[plan["id"]] = saved["id"]
        return saved

    def on_order_submitted(self, plan_id: str, order_id: str, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = self._get_record_for_plan(plan_id)
        if not record:
            return None
        updated = apply_order_submitted(record, order_id, order)
        saved = self._store.save(updated)
        with self._lock:
            self._by_entry_order[order_id] = saved["id"]
        return saved

    def on_entry_fill(self, order: Dict[str, Any], fill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = self._resolve_record_for_order(order)
        if not record:
            return None
        updated = apply_entry_fill(record, order, fill)
        return self._store.save(updated)

    def on_exit_fill(
        self,
        order: Dict[str, Any],
        fill: Dict[str, Any],
        *,
        exit_reason: str,
    ) -> Optional[Dict[str, Any]]:
        parent_id = order.get("parent_id")
        if not parent_id:
            return None
        record = self._get_record_for_entry_order(parent_id)
        if not record:
            return None
        updated = apply_exit_fill(record, order, fill, exit_reason=exit_reason)
        updated = apply_scoring(updated)
        saved = self._store.save(updated)
        self._mark_plan_completed(saved.get("plan_id"))
        return saved

    def get_by_plan_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        record_id = self._by_plan.get(plan_id)
        if record_id:
            return self._store.get(record_id)
        return self._store.get_by_plan_id(plan_id)

    def score_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        record = self._store.get(record_id)
        if not record:
            return None
        updated = apply_scoring(record)
        return self._store.save(updated)

    def score_by_plan_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        record = self.get_by_plan_id(plan_id)
        if not record:
            return None
        return self.score_record(record["id"])

    def on_manual_close(
        self,
        symbol: str,
        exit_price: float,
        *,
        quantity: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Finalize a replay record when a position is closed outside bracket exits."""
        record = self._find_open_record_for_symbol(symbol)
        if not record or record.get("status") != "filled":
            return None

        entry = (record.get("execution") or {}).get("entry") or {}
        qty = float(quantity or entry.get("quantity") or 0)
        synthetic_order = {
            "id": f"manual-close-{record['id'][:8]}",
            "parent_id": entry.get("order_id") or record.get("execution", {}).get("order_id"),
            "side": "sell",
            "filled_at": datetime.now().isoformat(),
        }
        fill = {"fill_price": exit_price, "quantity": qty}
        if not synthetic_order["parent_id"]:
            updated = apply_exit_fill(record, synthetic_order, fill, exit_reason="manual_close")
            updated = apply_scoring(updated)
            saved = self._store.save(updated)
            self._mark_plan_completed(saved.get("plan_id"))
            return saved
        result = self.on_exit_fill(synthetic_order, fill, exit_reason="manual_close")
        return result

    def reset(self) -> None:
        with self._lock:
            self._by_plan.clear()
            self._by_entry_order.clear()
        self._store.reset(clear_file=True)

    def _get_record_for_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        record_id = self._by_plan.get(plan_id)
        if record_id:
            record = self._store.get(record_id)
            if record:
                return record
        return self._store.get_by_plan_id(plan_id)

    def _get_record_for_entry_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        record_id = self._by_entry_order.get(order_id)
        if record_id:
            return self._store.get(record_id)
        record = self._find_record_by_entry_order(order_id)
        if record:
            with self._lock:
                self._by_entry_order[order_id] = record["id"]
        return record

    def _resolve_record_for_order(self, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = self._get_record_for_entry_order(order["id"])
        if record:
            return record
        plan_id = (order.get("trade_plan") or {}).get("plan_id")
        if plan_id:
            return self._get_record_for_plan(plan_id)
        return None

    def _find_record_by_entry_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        for record in self._store.list_all():
            execution = record.get("execution") or {}
            if execution.get("order_id") == order_id:
                return record
            entry = execution.get("entry") or {}
            if entry.get("order_id") == order_id:
                return record
        return None

    def _find_open_record_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = (symbol or "").upper()
        for record in self._store.list_all():
            if record.get("status") != "filled":
                continue
            market = record.get("market") or {}
            plan = record.get("trade_intent") or {}
            candidates = {
                market.get("instrument_id", "").upper(),
                market.get("symbol", "").upper(),
                plan.get("instrument_id", "").upper(),
                plan.get("symbol", "").upper(),
            }
            if key in candidates:
                return record
        return None

    def _index_loaded_records(self) -> None:
        for record in self._store.list_all():
            plan_id = record.get("plan_id")
            if plan_id:
                self._by_plan.setdefault(plan_id, record["id"])
            order_id = (record.get("execution") or {}).get("order_id")
            if order_id:
                self._by_entry_order.setdefault(order_id, record["id"])

    def _mark_plan_completed(self, plan_id: Optional[str]) -> None:
        if not plan_id:
            return
        from ..trading.trade_plan import get_trade_plan_manager

        manager = get_trade_plan_manager()
        plan = manager.get_plan(plan_id)
        if not plan or plan.get("status") == "COMPLETED":
            return
        if plan.get("status") == "ORDER_CREATED":
            manager.mark_completed(plan_id)


_memory_instance: Optional[ReplayMemory] = None


def get_replay_memory(store: Optional[ReplayStore] = None) -> ReplayMemory:
    global _memory_instance
    if store is not None:
        return ReplayMemory(store=store)
    if _memory_instance is None:
        _memory_instance = ReplayMemory()
    return _memory_instance


def reset_replay_memory() -> None:
    global _memory_instance
    if _memory_instance is not None:
        _memory_instance.reset()
    _memory_instance = None
