"""Trading skill rating based on performance and behavior."""

from typing import Any, Dict, List, Optional


class SkillScoreCalculator:
    """Calculate 0-100 skill score across four dimensions."""

    WEIGHTS = {
        "risk_management": 0.30,
        "consistency": 0.25,
        "strategy_quality": 0.25,
        "emotional_discipline": 0.20,
    }

    def calculate(
        self,
        performance: Optional[Dict[str, Any]] = None,
        backtest_results: Optional[Dict[str, Any]] = None,
        challenge_progress: Optional[List[Dict[str, Any]]] = None,
        trade_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        performance = performance or {}
        backtest_results = backtest_results or {}
        challenge_progress = challenge_progress or []
        trade_history = trade_history or []

        risk = self._score_risk_management(performance, backtest_results)
        consistency = self._score_consistency(performance, backtest_results)
        strategy = self._score_strategy_quality(backtest_results, performance)
        discipline = self._score_emotional_discipline(trade_history, challenge_progress)

        components = {
            "risk_management": risk,
            "consistency": consistency,
            "strategy_quality": strategy,
            "emotional_discipline": discipline,
        }

        total = sum(components[k] * self.WEIGHTS[k] for k in components)
        total = round(max(0, min(100, total)))

        return {
            "score": total,
            "level": self._level(total),
            "components": components,
            "feedback": self._feedback(components, total),
        }

    def _score_risk_management(
        self, performance: Dict[str, Any], backtest: Dict[str, Any]
    ) -> float:
        score = 50.0
        drawdown = performance.get("drawdown", backtest.get("max_drawdown", 0))
        if drawdown <= 3:
            score += 30
        elif drawdown <= 7:
            score += 15
        elif drawdown <= 10:
            score += 5
        else:
            score -= min(30, (drawdown - 10) * 2)

        sharpe = performance.get("sharpe_ratio", backtest.get("sharpe_ratio", 0))
        if sharpe > 1:
            score += 15
        elif sharpe > 0.5:
            score += 8
        elif sharpe < 0:
            score -= 10

        return max(0, min(100, score))

    def _score_consistency(
        self, performance: Dict[str, Any], backtest: Dict[str, Any]
    ) -> float:
        score = 40.0
        win_rate = performance.get("win_rate", backtest.get("win_rate", 0))
        total_trades = performance.get("total_trades", backtest.get("total_trades", 0))

        if total_trades >= 10:
            score += 15
        elif total_trades >= 5:
            score += 8

        if win_rate >= 55:
            score += 25
        elif win_rate >= 45:
            score += 15
        elif win_rate >= 35:
            score += 5
        else:
            score -= 10

        pf = performance.get("profit_factor", backtest.get("profit_factor"))
        if pf and pf >= 1.5:
            score += 15
        elif pf and pf >= 1.0:
            score += 8

        return max(0, min(100, score))

    def _score_strategy_quality(
        self, backtest: Dict[str, Any], performance: Dict[str, Any]
    ) -> float:
        score = 45.0
        bc = backtest.get("benchmark_comparison", performance.get("benchmark_comparison", {}))
        if bc.get("beat_benchmark"):
            score += 25
        elif bc.get("alpha", 0) is not None and bc.get("alpha", 0) > -2:
            score += 10
        else:
            score -= 15

        ret = backtest.get("total_return_pct", performance.get("total_return_pct", 0))
        if ret > 10:
            score += 20
        elif ret > 0:
            score += 10
        elif ret < -5:
            score -= 15

        return max(0, min(100, score))

    def _score_emotional_discipline(
        self, trades: List[Dict[str, Any]], challenges: List[Dict[str, Any]]
    ) -> float:
        score = 50.0
        completed = sum(1 for c in challenges if c.get("progress", {}).get("completed"))
        if completed >= 2:
            score += 25
        elif completed >= 1:
            score += 12

        if len(trades) > 30:
            score -= 15
        elif 5 <= len(trades) <= 20:
            score += 10

        return max(0, min(100, score))

    def _level(self, score: int) -> str:
        if score >= 80:
            return "Expert"
        if score >= 65:
            return "Advanced"
        if score >= 45:
            return "Intermediate"
        if score >= 25:
            return "Beginner"
        return "Novice"

    def _feedback(self, components: Dict[str, float], total: int) -> List[str]:
        feedback = []
        weakest = min(components, key=components.get)
        labels = {
            "risk_management": "Risk Management",
            "consistency": "Consistency",
            "strategy_quality": "Strategy Quality",
            "emotional_discipline": "Emotional Discipline",
        }
        feedback.append(f"Focus area: {labels[weakest]} ({components[weakest]:.0f}/100).")

        if total >= 70:
            feedback.append("Strong overall performance — keep refining entries.")
        elif total >= 45:
            feedback.append("Solid foundation — backtest more strategies in the Lab.")
        else:
            feedback.append("Keep practicing in replay mode and complete challenges.")

        return feedback
