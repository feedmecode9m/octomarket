"""Price and indicator alerts for paper trading practice."""

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class AlertManager:
    """Manage and evaluate trading alerts."""

    def __init__(self):
        self._lock = threading.RLock()
        self._alerts: List[Dict[str, Any]] = []
        self._triggered: List[Dict[str, Any]] = []

    def create(
        self,
        symbol: str,
        alert_type: str,
        condition: str,
        threshold: float,
        message: str = "",
    ) -> Dict[str, Any]:
        alert = {
            "id": str(uuid.uuid4()),
            "symbol": symbol.upper(),
            "type": alert_type,
            "condition": condition,
            "threshold": threshold,
            "message": message or f"{symbol} {condition} {threshold}",
            "active": True,
            "created_at": datetime.now().isoformat(),
            "triggered_at": None,
        }
        with self._lock:
            self._alerts.append(alert)
        return alert.copy()

    def delete(self, alert_id: str) -> bool:
        with self._lock:
            for i, a in enumerate(self._alerts):
                if a["id"] == alert_id:
                    del self._alerts[i]
                    return True
            return False

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.copy() for a in self._alerts]

    def get_triggered(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.copy() for t in self._triggered[-20:]]

    def check_price_alerts(self, symbol: str, price: float, prev_close: float) -> List[Dict[str, Any]]:
        triggered = []
        if prev_close <= 0:
            return triggered

        change_pct = (price - prev_close) / prev_close * 100

        with self._lock:
            for alert in self._alerts:
                if not alert["active"] or alert["symbol"] != symbol.upper():
                    continue
                if alert["type"] != "price":
                    continue

                fired = False
                if alert["condition"] == "drops" and change_pct <= -alert["threshold"]:
                    fired = True
                elif alert["condition"] == "rises" and change_pct >= alert["threshold"]:
                    fired = True
                elif alert["condition"] == "above" and price >= alert["threshold"]:
                    fired = True
                elif alert["condition"] == "below" and price <= alert["threshold"]:
                    fired = True

                if fired:
                    alert["active"] = False
                    alert["triggered_at"] = datetime.now().isoformat()
                    event = {**alert, "trigger_price": price, "change_percent": round(change_pct, 2)}
                    self._triggered.append(event)
                    triggered.append(event)

        return triggered

    def check_indicator_alerts(self, symbol: str, rsi: Optional[float] = None) -> List[Dict[str, Any]]:
        triggered = []
        with self._lock:
            for alert in self._alerts:
                if not alert["active"] or alert["symbol"] != symbol.upper():
                    continue
                if alert["type"] != "indicator" or rsi is None:
                    continue

                fired = False
                if alert["condition"] == "below" and rsi < alert["threshold"]:
                    fired = True
                elif alert["condition"] == "above" and rsi > alert["threshold"]:
                    fired = True

                if fired:
                    alert["active"] = False
                    alert["triggered_at"] = datetime.now().isoformat()
                    event = {**alert, "rsi_value": rsi}
                    self._triggered.append(event)
                    triggered.append(event)

        return triggered

    def check_portfolio_risk(self, risk_score: float, threshold: float = 70) -> Optional[Dict[str, Any]]:
        if risk_score >= threshold:
            event = {
                "id": str(uuid.uuid4()),
                "type": "portfolio_risk",
                "symbol": "PORTFOLIO",
                "message": f"Portfolio risk score {risk_score:.0f} exceeds threshold {threshold}",
                "risk_score": risk_score,
                "triggered_at": datetime.now().isoformat(),
            }
            with self._lock:
                self._triggered.append(event)
            return event
        return None


_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AlertManager()
    return _manager_instance
