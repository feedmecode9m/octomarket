"""Research report persistence."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_RESEARCH_DIR = Path(__file__).resolve().parents[2] / "data" / "research"
DEFAULT_REPORTS_FILE = "reports.jsonl"


class ResearchReportStore:
    """Store strategy research reports as JSON lines."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else DEFAULT_RESEARCH_DIR / DEFAULT_REPORTS_FILE
        self._lock = threading.RLock()
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._load()

    def save(self, report: Dict[str, Any]) -> Dict[str, Any]:
        report_id = (
            report.get("comparison_id")
            or report.get("walk_forward_id")
            or report.get("report_id")
        )
        if not report_id:
            raise ValueError("Report must include report_id, comparison_id, or walk_forward_id")
        with self._lock:
            self._reports[report_id] = json.loads(json.dumps(report))
            self._persist()
        return self.get(report_id) or report

    def get(self, report_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._reports.get(report_id)
            return json.loads(json.dumps(item)) if item else None

    def latest_comparison(
        self,
        instrument_id: str,
        *,
        period: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            items = [
                r for r in self._reports.values()
                if r.get("report_type") == "comparison"
                and r.get("instrument_id", "").upper() == instrument_id.upper()
                and (not period or r.get("period") == period)
            ]
            if not items:
                return None
            items.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
            return json.loads(json.dumps(items[0]))

    def latest_for_strategy(
        self,
        strategy_id: str,
        *,
        instrument_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            items = [
                r for r in self._reports.values()
                if r.get("strategy_id") == strategy_id
                and (not instrument_id or r.get("instrument_id", "").upper() == instrument_id.upper())
            ]
            if not items:
                return None
            items.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
            return json.loads(json.dumps(items[0]))

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(self._reports.values(), key=lambda r: r.get("generated_at", ""), reverse=True)
            return [json.loads(json.dumps(i)) for i in items]

    def reset(self) -> None:
        with self._lock:
            self._reports.clear()
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
                report = json.loads(line)
                rid = report.get("comparison_id") or report.get("walk_forward_id") or report.get("report_id")
                if rid:
                    self._reports[rid] = report

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        items = sorted(self._reports.values(), key=lambda r: r.get("generated_at", ""))
        with tmp.open("w", encoding="utf-8") as handle:
            for report in items:
                handle.write(json.dumps(report, separators=(",", ":")))
                handle.write("\n")
        os.replace(tmp, self._path)


_store_instance: Optional[ResearchReportStore] = None


def get_research_report_store(path: Optional[Path] = None) -> ResearchReportStore:
    global _store_instance
    if path is not None:
        return ResearchReportStore(path=path)
    if _store_instance is None:
        _store_instance = ResearchReportStore()
    return _store_instance


def reset_research_report_store() -> None:
    global _store_instance
    if _store_instance is not None:
        _store_instance.reset()
    _store_instance = None
