"""Market scenario training exercises."""

from typing import Any, Dict, List, Optional


SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Market Drops 10%",
        "description": "The market has dropped 10% in two weeks. Your portfolio is down 8%. Volatility is rising.",
        "context": {
            "market_change_pct": -10,
            "portfolio_change_pct": -8,
            "volatility": "high",
        },
        "question": "What do you do?",
        "options": [
            {"id": "a", "text": "Sell everything", "action": "sell_all"},
            {"id": "b", "text": "Reduce position sizes", "action": "reduce"},
            {"id": "c", "text": "Hold and wait", "action": "hold"},
            {"id": "d", "text": "Buy more (averaging down)", "action": "buy_more"},
        ],
        "scores": {
            "sell_all": {"decision_quality": 30, "risk_awareness": 50, "reasoning": "Panic selling locks in losses — rarely the best move."},
            "reduce": {"decision_quality": 90, "risk_awareness": 95, "reasoning": "Reducing exposure during drawdowns protects capital while staying engaged."},
            "hold": {"decision_quality": 70, "risk_awareness": 60, "reasoning": "Holding is reasonable if your thesis is intact, but monitor closely."},
            "buy_more": {"decision_quality": 40, "risk_awareness": 30, "reasoning": "Averaging down without a plan can compound losses in a downtrend."},
        },
        "best_action": "reduce",
    },
    {
        "id": 2,
        "title": "Stock Gaps Up 15%",
        "description": "Your watchlist stock gapped up 15% on positive news before market open. You don't own it yet.",
        "context": {
            "gap_pct": 15,
            "news": "positive earnings surprise",
            "rsi_estimate": 78,
        },
        "question": "What is your best course of action?",
        "options": [
            {"id": "a", "text": "Buy immediately at open", "action": "buy_open"},
            {"id": "b", "text": "Wait for a pullback to support", "action": "wait_pullback"},
            {"id": "c", "text": "Short the gap fill", "action": "short"},
            {"id": "d", "text": "Skip this trade entirely", "action": "skip"},
        ],
        "scores": {
            "buy_open": {"decision_quality": 35, "risk_awareness": 25, "reasoning": "Chasing a 15% gap means buying at overbought levels with poor risk/reward."},
            "wait_pullback": {"decision_quality": 85, "risk_awareness": 90, "reasoning": "Patience for a pullback improves entry price and risk/reward."},
            "short": {"decision_quality": 50, "risk_awareness": 40, "reasoning": "Fading a strong gap on good news is risky for beginners."},
            "skip": {"decision_quality": 75, "risk_awareness": 80, "reasoning": "Skipping when no clear edge exists is disciplined trading."},
        },
        "best_action": "wait_pullback",
    },
    {
        "id": 3,
        "title": "High Volatility Earnings Event",
        "description": "A stock you hold reports earnings after close today. Implied volatility is 2x normal. Position is 8% of portfolio.",
        "context": {
            "event": "earnings",
            "iv_multiplier": 2.0,
            "position_pct": 8,
        },
        "question": "How do you manage this?",
        "options": [
            {"id": "a", "text": "Hold full position through earnings", "action": "hold_full"},
            {"id": "b", "text": "Reduce to 3% before earnings", "action": "reduce"},
            {"id": "c", "text": "Sell entire position before earnings", "action": "sell_all"},
            {"id": "d", "text": "Add to position before earnings", "action": "add"},
        ],
        "scores": {
            "hold_full": {"decision_quality": 45, "risk_awareness": 35, "reasoning": "8% through a binary event is excessive risk for a learning account."},
            "reduce": {"decision_quality": 95, "risk_awareness": 95, "reasoning": "Sizing down before binary events is professional risk management."},
            "sell_all": {"decision_quality": 70, "risk_awareness": 85, "reasoning": "Eliminating event risk is valid, but may miss upside if thesis is strong."},
            "add": {"decision_quality": 15, "risk_awareness": 10, "reasoning": "Adding before earnings with elevated IV is gambling, not trading."},
        },
        "best_action": "reduce",
    },
]


class ScenarioTrainer:
    """Score user decisions on market scenarios."""

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": s["id"],
                "title": s["title"],
                "description": s["description"],
                "question": s["question"],
                "option_count": len(s["options"]),
            }
            for s in SCENARIOS
        ]

    def get_scenario(self, scenario_id: int) -> Optional[Dict[str, Any]]:
        for s in SCENARIOS:
            if s["id"] == scenario_id:
                return {
                    "id": s["id"],
                    "title": s["title"],
                    "description": s["description"],
                    "context": s["context"],
                    "question": s["question"],
                    "options": s["options"],
                }
        return None

    def score_answer(self, scenario_id: int, action: str, reasoning: str = "") -> Dict[str, Any]:
        scenario = None
        for s in SCENARIOS:
            if s["id"] == scenario_id:
                scenario = s
                break
        if not scenario:
            return {"error": "Scenario not found"}

        scores = scenario["scores"].get(action)
        if not scores:
            return {"error": "Invalid action"}

        best = scenario["best_action"]
        overall = round(
            (scores["decision_quality"] + scores["risk_awareness"]) / 2
        )

        return {
            "scenario_id": scenario_id,
            "action": action,
            "decision_quality": scores["decision_quality"],
            "risk_awareness": scores["risk_awareness"],
            "overall_score": overall,
            "feedback": scores["reasoning"],
            "best_action": best,
            "was_optimal": action == best,
            "user_reasoning": reasoning,
        }


_trainer_instance: Optional[ScenarioTrainer] = None


def get_scenario_trainer() -> ScenarioTrainer:
    global _trainer_instance
    if _trainer_instance is None:
        _trainer_instance = ScenarioTrainer()
    return _trainer_instance
