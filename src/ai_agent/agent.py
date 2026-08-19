"""Trading Coach Agent — educational AI for paper trading."""

from typing import Any, Dict, List, Optional

from .market_analyzer import MarketAnalyzer
from .risk_coach import RiskCoach
from .trade_journal import TradeJournal, get_trade_journal


class TradingCoachAgent:
    """Receives market state, explains possible actions, and generates educational feedback."""

    def __init__(
        self,
        market_analyzer: Optional[MarketAnalyzer] = None,
        risk_coach: Optional[RiskCoach] = None,
        trade_journal: Optional[TradeJournal] = None,
    ):
        self.market_analyzer = market_analyzer or MarketAnalyzer()
        self.risk_coach = risk_coach or RiskCoach()
        self.trade_journal = trade_journal or get_trade_journal()

    def analyze_market(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        portfolio: Dict[str, Any],
        prices: Optional[List[float]] = None,
        strategy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze current market state and return educational guidance."""
        if not symbol:
            raise ValueError("Symbol is required")

        market_analysis = self.market_analyzer.analyze(indicators, prices)
        risk_assessment = self.risk_coach.assess_risk(portfolio, indicators, strategy)

        market_summary = self._build_market_summary(symbol, market_analysis)
        possible_scenarios = self._build_scenarios(market_analysis, risk_assessment)
        risk_warning = self._build_risk_warning(risk_assessment)
        learning_points = self._build_learning_points(market_analysis, risk_assessment)
        possible_actions = self._explain_possible_actions(market_analysis, risk_assessment, portfolio)

        return {
            "symbol": symbol.upper(),
            "market_summary": market_summary,
            "current_trend": market_analysis["trend"],
            "risk_level": risk_assessment["risk_level"],
            "possible_scenarios": possible_scenarios,
            "possible_actions": possible_actions,
            "risk_warning": risk_warning,
            "learning_points": learning_points,
            "strategy_explanation": self._explain_strategy(strategy or {}),
            "analysis_details": {
                "market": market_analysis,
                "risk": risk_assessment,
            },
        }

    def review_trade(
        self,
        trade_history: List[Dict[str, Any]],
        strategy: Optional[Dict[str, Any]] = None,
        outcome: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review trade history and provide educational feedback."""
        strategy = strategy or {}
        outcome = outcome or {}

        mistakes = self._identify_mistakes(trade_history, outcome)
        strengths = self._identify_strengths(trade_history, outcome)
        improvement_plan = self._build_improvement_plan(mistakes, strategy, outcome)
        journal_feedback = self._generate_journal_feedback(trade_history, outcome)

        return {
            "mistakes": mistakes,
            "strengths": strengths,
            "improvement_plan": improvement_plan,
            "journal_feedback": journal_feedback,
            "trade_count": len(trade_history),
        }

    def _build_market_summary(self, symbol: str, analysis: Dict[str, Any]) -> str:
        trend = analysis["trend"]
        ma = analysis["moving_averages"]
        rsi = analysis["rsi"]

        parts = [f"{symbol.upper()} is showing a {trend} trend."]
        if ma.get("explanation"):
            parts.append(ma["explanation"])
        if rsi.get("explanation"):
            parts.append(rsi["explanation"])

        return " ".join(parts)

    def _build_scenarios(self, analysis: Dict[str, Any], risk: Dict[str, Any]) -> List[str]:
        scenarios = []
        trend = analysis["trend"]

        if trend == "bullish":
            scenarios.append("Bullish continuation: price holds above the short MA and RSI stays below 70.")
            scenarios.append("Pullback entry: price retraces to the long MA support before resuming upward.")
        elif trend == "bearish":
            scenarios.append("Bearish continuation: price stays below the short MA with declining momentum.")
            scenarios.append("Relief rally: oversold RSI triggers a short-term bounce — not necessarily a reversal.")
        else:
            scenarios.append("Range-bound: price oscillates between support and resistance — avoid chasing breakouts without volume.")
            scenarios.append("Breakout pending: moving averages converging — watch for a directional move.")

        vol = analysis["volatility"]
        if vol.get("level") == "high":
            scenarios.append("High volatility scenario: wider stops needed; consider smaller position sizes.")

        return scenarios

    def _build_risk_warning(self, risk: Dict[str, Any]) -> str:
        warnings = risk.get("warnings", [])
        level = risk.get("risk_level", "moderate")
        return f"Risk level: {level.upper()}. " + " ".join(warnings)

    def _build_learning_points(self, analysis: Dict[str, Any], risk: Dict[str, Any]) -> List[str]:
        points = []

        ma = analysis["moving_averages"]
        if ma.get("signal") == "bullish":
            points.append("Lesson: A golden cross (short MA > long MA) is a classic trend-following buy signal.")
        elif ma.get("signal") == "bearish":
            points.append("Lesson: A death cross (short MA < long MA) warns of potential downtrends.")

        rsi = analysis["rsi"]
        if rsi.get("zone") == "overbought":
            points.append("Lesson: RSI above 70 suggests overbought conditions — patience often beats FOMO.")
        elif rsi.get("zone") == "oversold":
            points.append("Lesson: RSI below 30 can signal oversold bounces, but always confirm with price action.")

        rr = risk.get("risk_reward", {})
        if rr.get("quality") == "poor":
            points.append("Lesson: Your current risk/reward ratio is below 1:1 — consider wider profit targets or tighter stops.")

        dd = risk.get("drawdown", {})
        if dd.get("severity") == "high":
            points.append("Lesson: Large drawdowns compound losses. Reducing position size is the fastest recovery tool.")

        vol = analysis["volatility"]
        if vol.get("level") == "high":
            points.append("Lesson: High volatility means larger price swings — adjust stop losses accordingly.")

        if not points:
            points.append("Lesson: Always define your entry, stop loss, and profit target before placing a trade.")

        return points

    def _explain_possible_actions(
        self,
        analysis: Dict[str, Any],
        risk: Dict[str, Any],
        portfolio: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        actions = []
        trend = analysis["trend"]
        shares = int(portfolio.get("shares_held", 0) or 0)
        risk_level = risk.get("risk_level", "moderate")

        if trend == "bullish" and shares == 0:
            actions.append({
                "action": "consider_buy",
                "explanation": "Bullish trend with no position. A buy signal may appear on MA crossover with RSI confirmation.",
            })
        elif trend == "bullish" and shares > 0:
            actions.append({
                "action": "hold",
                "explanation": "You're in a winning trend. Consider trailing your stop loss to lock in gains.",
            })
        elif trend == "bearish" and shares > 0:
            actions.append({
                "action": "consider_sell",
                "explanation": "Bearish trend with open position. Review your stop loss — protecting capital comes first.",
            })
        elif trend == "bearish" and shares == 0:
            actions.append({
                "action": "wait",
                "explanation": "Bearish trend — patience is key. Wait for trend reversal signals before buying.",
            })
        else:
            actions.append({
                "action": "observe",
                "explanation": "Neutral trend — no clear edge. Use this time to study charts and review your journal.",
            })

        if risk_level == "high":
            actions.append({
                "action": "reduce_risk",
                "explanation": "High risk environment detected. Consider smaller positions or staying in cash.",
            })

        return actions

    def _explain_strategy(self, strategy: Dict[str, Any]) -> str:
        short_w = strategy.get("short_window", 5)
        long_w = strategy.get("long_window", 20)
        profit = strategy.get("profit_threshold", 0.02)
        stop = strategy.get("stop_loss", 0.01)

        return (
            f"This simulator uses a Moving Average Crossover strategy: "
            f"buy when the {short_w}-period MA crosses above the {long_w}-period MA "
            f"(confirmed by RSI and momentum), sell on death cross or at {profit:.0%} profit / {stop:.0%} stop loss. "
            f"Position sizing risks ~{strategy.get('risk_per_trade', 0.02):.0%} of portfolio per trade."
        )

    def _identify_mistakes(
        self, trade_history: List[Dict[str, Any]], outcome: Dict[str, Any]
    ) -> List[str]:
        mistakes = []

        if not trade_history:
            mistakes.append("No trades recorded yet — start the simulator to practice decision-making.")
            return mistakes

        buys = [t for t in trade_history if t.get("type") == "buy"]
        sells = [t for t in trade_history if t.get("type") == "sell"]

        if len(buys) > len(sells) + 2:
            mistakes.append("Multiple open buy positions without corresponding sells — ensure every entry has an exit plan.")

        win_rate = outcome.get("win_rate", 0)
        if win_rate < 40 and len(trade_history) >= 4:
            mistakes.append(
                f"Win rate is {win_rate:.0f}% — review whether you're entering against the trend or ignoring RSI filters."
            )

        max_dd = outcome.get("max_drawdown", 0)
        if max_dd > 10:
            mistakes.append(
                f"Max drawdown of {max_dd:.1f}% is high — reduce position sizes or tighten stop losses."
            )

        total_return = outcome.get("total_return_pct", 0)
        if total_return < 0 and len(trade_history) >= 6:
            mistakes.append("Negative overall return — consider waiting for stronger signals before entering trades.")

        if len(buys) > 10:
            mistakes.append("High trade frequency — overtrading erodes returns through poor entries and fees (in real trading).")

        if not mistakes:
            mistakes.append("No major mistakes detected — keep refining entries and maintaining discipline.")

        return mistakes

    def _identify_strengths(
        self, trade_history: List[Dict[str, Any]], outcome: Dict[str, Any]
    ) -> List[str]:
        strengths = []

        if not trade_history:
            return ["Ready to start — your journal will track every decision for review."]

        win_rate = outcome.get("win_rate", 0)
        if win_rate >= 50:
            strengths.append(f"Win rate of {win_rate:.0f}% shows good trade selection.")

        total_return = outcome.get("total_return_pct", 0)
        if total_return > 0:
            strengths.append(f"Positive return of {total_return:.1f}% — strategy is working in current conditions.")

        max_dd = outcome.get("max_drawdown", 0)
        if max_dd < 5:
            strengths.append(f"Low drawdown ({max_dd:.1f}%) — excellent risk control.")

        if len(trade_history) >= 4 and len(trade_history) <= 20:
            strengths.append("Reasonable trade frequency — quality over quantity.")

        if not strengths:
            strengths.append("You're building experience — every trade in the journal is a learning opportunity.")

        return strengths

    def _build_improvement_plan(
        self, mistakes: List[str], strategy: Dict[str, Any], outcome: Dict[str, Any]
    ) -> List[str]:
        plan = [
            "Review each trade in your journal — note why you entered and whether the thesis played out.",
            "Paper trade for at least 20 sessions before changing strategy parameters.",
        ]

        if outcome.get("win_rate", 100) < 50:
            plan.append("Focus on Lesson 3 (RSI) — avoid buying when RSI is above 70.")

        if outcome.get("max_drawdown", 0) > 5:
            plan.append("Study Lesson 5 (Risk Management) — implement strict 1-2% risk per trade.")

        if strategy.get("short_window", 5) < 5:
            plan.append("Try increasing the short MA window to reduce false signals in choppy markets.")

        plan.append("Use historical mode to backtest strategy changes before applying them live.")

        return plan

    def _generate_journal_feedback(
        self, trade_history: List[Dict[str, Any]], outcome: Dict[str, Any]
    ) -> str:
        if not trade_history:
            return "Your trade journal is empty. Start the simulator and every trade will be recorded with educational context."

        self.trade_journal.sync_from_trades(trade_history)
        summary = self.trade_journal.get_summary()

        feedback = (
            f"Journal: {summary['total_entries']} entries, "
            f"{summary['closed_trades']} closed, win rate {summary['win_rate']}%."
        )

        if summary["recent_lessons"]:
            feedback += f" Recent lesson: {summary['recent_lessons'][-1]}"
        elif outcome.get("total_return_pct", 0) > 0:
            feedback += " Keep documenting what works — patterns in your journal reveal your edge."
        else:
            feedback += " After each losing trade, write one sentence about what you'd do differently."

        return feedback
