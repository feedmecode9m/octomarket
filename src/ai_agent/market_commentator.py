"""Live market commentary during paper trading sessions."""

from typing import Any, Dict, List, Optional

from ..market.watchlist import get_sector


class MarketCommentator:
    """Provide contextual AI commentary on portfolio and market state."""

    def commentate(
        self,
        portfolio: Dict[str, Any],
        watchlist: List[Dict[str, Any]],
        session_state: Optional[Dict[str, Any]] = None,
        alerts_triggered: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        comments = []
        warnings = []
        suggestions = []

        positions = portfolio.get("positions", {})
        total_value = portfolio.get("total_value", 0)
        risk_score = portfolio.get("risk_score", 0)

        comments.extend(self._concentration_comments(positions, total_value))
        comments.extend(self._sector_comments(positions, total_value))
        comments.extend(self._allocation_comments(positions, total_value, portfolio.get("cash", 0)))
        comments.extend(self._risk_reward_comments(positions))
        warnings.extend(self._risk_warnings(risk_score, portfolio))
        suggestions.extend(self._session_suggestions(session_state, watchlist))

        if alerts_triggered:
            for a in alerts_triggered:
                warnings.append(f"Alert triggered: {a.get('message', a.get('type', 'unknown'))}")

        return {
            "commentary": comments,
            "warnings": warnings,
            "suggestions": suggestions,
            "summary": comments[0] if comments else "Markets are active — review your watchlist and plan before trading.",
        }

    def _concentration_comments(self, positions: Dict, total_value: float) -> List[str]:
        comments = []
        if not positions or total_value <= 0:
            return ["No open positions — consider starting with 1-2 high-conviction ideas."]

        for sym, pos in positions.items():
            mv = pos.get("market_value", 0)
            pct = mv / total_value * 100 if total_value > 0 else 0
            if pct > 40:
                comments.append(
                    f"Your portfolio is {pct:.0f}% concentrated in {sym}. Consider diversification."
                )
            elif pct > 25:
                comments.append(
                    f"{sym} represents {pct:.0f}% of your portfolio — monitor concentration risk."
                )

        sector_pcts = self._sector_exposure(positions, total_value)
        for sector, pct in sector_pcts.items():
            if pct > 60:
                comments.append(
                    f"Your portfolio is {pct:.0f}% concentrated in {sector}. Consider diversification."
                )
        return comments

    def _sector_comments(self, positions: Dict, total_value: float) -> List[str]:
        sector_pcts = self._sector_exposure(positions, total_value)
        comments = []
        if len(sector_pcts) == 1 and positions:
            sector = list(sector_pcts.keys())[0]
            comments.append(f"All holdings are in {sector} — a single sector downturn would hit hard.")
        return comments

    def _allocation_comments(self, positions: Dict, total_value: float, cash: float) -> List[str]:
        if total_value <= 0:
            return []
        cash_pct = cash / total_value * 100
        if cash_pct < 10:
            return ["Cash reserves below 10% — limited flexibility for new opportunities or averaging down."]
        if cash_pct > 80:
            return [f"{cash_pct:.0f}% in cash — capital is idle. Consider planned entries when signals align."]
        return []

    def _risk_reward_comments(self, positions: Dict) -> List[str]:
        comments = []
        for sym, pos in positions.items():
            avg = pos.get("avg_cost", 0)
            current = pos.get("current_price", 0)
            if avg > 0 and current > 0:
                gain_pct = (current - avg) / avg * 100
                stop = avg * 0.99
                target = avg * 1.03
                risk = avg - stop
                reward = target - avg
                if risk > 0:
                    ratio = reward / risk
                    comments.append(
                        f"{sym}: Stop at ${stop:.2f} vs target ${target:.2f} creates a {ratio:.0f}:1 reward/risk ratio."
                    )
                if gain_pct > 5:
                    comments.append(f"{sym} is up {gain_pct:.1f}% — consider trailing your stop to lock in gains.")
        return comments[:3]

    def _risk_warnings(self, risk_score: float, portfolio: Dict) -> List[str]:
        warnings = []
        if risk_score >= 70:
            warnings.append(f"Portfolio risk score is {risk_score:.0f}/100 — consider reducing exposure.")
        dd = portfolio.get("total_return_pct", 0)
        if dd < -5:
            warnings.append(f"Portfolio down {abs(dd):.1f}% — review recent trades before adding risk.")
        return warnings

    def _session_suggestions(
        self, session_state: Optional[Dict], watchlist: List[Dict]
    ) -> List[str]:
        suggestions = []
        if session_state:
            state = session_state.get("state", "")
            if state == "pre_market":
                suggestions.append("Pre-market: review your watchlist and set alerts before the open.")
            elif state == "open":
                suggestions.append("Market is open — stick to your plan and position sizing rules.")
            elif state == "closed":
                suggestions.append("Session closed — review trades in your journal and note lessons learned.")

        bullish = sum(1 for w in watchlist if w.get("trend") == "bullish")
        bearish = sum(1 for w in watchlist if w.get("trend") == "bearish")
        if bearish > bullish:
            suggestions.append("Most watchlist stocks are bearish — be selective with new long entries.")
        return suggestions

    def _sector_exposure(self, positions: Dict, total_value: float) -> Dict[str, float]:
        sectors: Dict[str, float] = {}
        for sym, pos in positions.items():
            sector = get_sector(sym)
            mv = pos.get("market_value", 0)
            sectors[sector] = sectors.get(sector, 0) + mv
        if total_value > 0:
            return {s: round(v / total_value * 100, 1) for s, v in sectors.items()}
        return sectors


_commentator_instance: Optional[MarketCommentator] = None


def get_market_commentator() -> MarketCommentator:
    global _commentator_instance
    if _commentator_instance is None:
        _commentator_instance = MarketCommentator()
    return _commentator_instance
