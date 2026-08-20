"""Walk-forward performance degradation flags — warnings, not auto-rejects."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEGRADATION_RATIO = 0.7


def assess_performance_degradation(windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Flag research → validation → OOS profit-factor decline without rejecting the strategy."""
    by_name: Dict[str, Dict[str, Any]] = {}
    for item in windows or []:
        window = item.get("window") or {}
        name = window.get("name")
        if name:
            by_name[name] = item.get("report") or {}

    research_pf = _pf(by_name.get("research"))
    validation_pf = _pf(by_name.get("validation"))
    oos_pf = _pf(by_name.get("out_of_sample"))

    warnings: List[str] = []
    detected = False

    if research_pf is not None and oos_pf is not None and oos_pf < research_pf * DEGRADATION_RATIO:
        detected = True
        warnings.append(
            f"Performance degradation detected: research PF {research_pf} vs out-of-sample PF {oos_pf}."
        )
    elif (
        research_pf is not None
        and validation_pf is not None
        and validation_pf < research_pf * DEGRADATION_RATIO
    ):
        detected = True
        warnings.append(
            f"Performance degradation detected: research PF {research_pf} vs validation PF {validation_pf}."
        )

    return {
        "detected": detected,
        "research_pf": research_pf,
        "validation_pf": validation_pf,
        "oos_pf": oos_pf,
        "warnings": warnings,
    }


def _pf(report: Optional[Dict[str, Any]]) -> Optional[float]:
    if not report:
        return None
    value = report.get("profit_factor")
    return float(value) if value is not None else None
