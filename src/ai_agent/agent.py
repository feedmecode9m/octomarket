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

    def pre_trade_review(
        self,
        action: str,
        symbol: str,
        market_state: Dict[str, Any],
        portfolio: Dict[str, Any],
        reason: str = "",
        strategy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review a planned trade before execution — 'Why are you entering?'"""
        indicators = market_state.get("indicators", market_state)
        analysis = self.market_analyzer.analyze(indicators, market_state.get("prices"))
        risk = self.risk_coach.assess_risk(portfolio, indicators, strategy)
        confidence = self.trade_confidence_score(indicators, strategy or {}, risk["risk_level"], analysis)

        action = action.upper()
        questions = []
        guidance = []

        if action == "BUY":
            questions.append("Why are you entering this trade now?")
            questions.append("Where is your stop loss and profit target?")
            if analysis["trend"] == "bearish":
                guidance.append("Caution: trend is bearish — buying against the trend requires strong justification.")
            if analysis["rsi"].get("zone") == "overbought":
                guidance.append("RSI is overbought — consider waiting for a pullback.")
            if not reason:
                guidance.append("Write your reason before entering — undisciplined entries are the #1 beginner mistake.")
        elif action == "SELL":
            questions.append("Why are you exiting — target hit, stop loss, or thesis invalidated?")
            if analysis["trend"] == "bullish":
                guidance.append("Trend is still bullish — make sure you're not selling too early out of fear.")
        else:
            questions.append("Why hold? Is waiting for a clearer signal the right choice?")
            guidance.append("Holding is valid when no edge exists — patience is a skill.")

        return {
            "action": action,
            "symbol": symbol.upper(),
            "prompt": "Why are you entering?" if action == "BUY" else "Why are you exiting?" if action == "SELL" else "Why hold?",
            "questions": questions,
            "guidance": guidance,
            "trade_confidence_score": confidence,
            "market_trend": analysis["trend"],
            "risk_level": risk["risk_level"],
            "approved": confidence >= 40 or action == "HOLD",
            "user_reason": reason,
        }

    def post_trade_review(
        self,
        trade: Dict[str, Any],
        outcome: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review a completed trade — 'What happened?'"""
        outcome = outcome or {}
        action = trade.get("action", trade.get("type", "")).upper()
        fill_price = trade.get("fill_price", trade.get("price", 0))
        pnl = trade.get("realized_pnl", outcome.get("pnl", 0))

        reflection = []
        lessons = []

        if action == "BUY":
            reflection.append(f"You entered {trade.get('symbol', '')} at ${fill_price:.2f}.")
            reflection.append("What happened? Monitor whether price respects your thesis.")
        elif action == "SELL":
            reflection.append(f"You exited at ${fill_price:.2f}.")
            if pnl and float(pnl) > 0:
                reflection.append("What happened? Profitable exit — note what confirmed your thesis.")
                lessons.append("Winning trade: document the setup so you can repeat it.")
            elif pnl and float(pnl) < 0:
                reflection.append("What happened? Loss taken — review if stop was appropriate.")
                lessons.append("Losing trade: write one sentence about what you'd do differently.")
            else:
                reflection.append("What happened? Review whether the exit matched your plan.")

        commission = trade.get("commission", 0)
        if commission:
            lessons.append(f"Commission cost ${commission:.2f} — factor fees into every trade plan.")

        return {
            "prompt": "What happened?",
            "reflection": reflection,
            "lessons": lessons,
            "trade": trade,
            "outcome_summary": outcome,
        }

    def trade_confidence_score(
        self,
        indicators: Dict[str, Any],
        strategy: Dict[str, Any],
        risk_level: str = "moderate",
        market_analysis: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Score 0-100 based on strategy alignment, risk level, and market conditions."""
        score = 50

        if market_analysis is None:
            market_analysis = self.market_analyzer.analyze(indicators)

        trend = market_analysis.get("trend", "neutral")
        rsi_zone = market_analysis.get("rsi", {}).get("zone", "neutral")

        if trend == "bullish":
            score += 15
        elif trend == "bearish":
            score -= 10

        if rsi_zone == "neutral":
            score += 10
        elif rsi_zone == "overbought":
            score -= 15
        elif rsi_zone == "oversold":
            score += 5

        momentum_dir = market_analysis.get("momentum", {}).get("direction", "flat")
        if momentum_dir in ("up", "strong_up"):
            score += 10
        elif momentum_dir in ("down", "strong_down"):
            score -= 10

        if risk_level == "low":
            score += 10
        elif risk_level == "high":
            score -= 20

        vol_level = market_analysis.get("volatility", {}).get("level", "moderate")
        if vol_level == "high":
            score -= 5

        return max(0, min(100, score))

    def review_strategy(
        self,
        strategy: Dict[str, Any],
        backtest_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Review a strategy design and its backtest results."""
        name = strategy.get("name", "Your Strategy")
        rules = strategy.get("rules", [])

        strengths = []
        weaknesses = []
        risks = []
        suggestions = []

        win_rate = backtest_results.get("win_rate", 0)
        drawdown = backtest_results.get("max_drawdown", 0)
        total_return = backtest_results.get("total_return_pct", 0)
        sharpe = backtest_results.get("sharpe_ratio", 0)
        total_trades = backtest_results.get("total_trades", 0)
        bc = backtest_results.get("benchmark_comparison", {})

        if win_rate >= 50:
            strengths.append(f"Win rate of {win_rate:.0f}% shows decent entry timing.")
        if total_return > 0:
            strengths.append(f"Positive return of {total_return:.1f}% over the backtest period.")
        if drawdown < 5:
            strengths.append(f"Low drawdown ({drawdown:.1f}%) — good risk control built in.")
        if sharpe > 0.5:
            strengths.append(f"Sharpe ratio of {sharpe:.2f} indicates acceptable risk-adjusted returns.")
        if len(rules) >= 2:
            strengths.append("Multi-rule strategy provides both entry and exit logic.")

        if win_rate >= 50 and drawdown > 10:
            weaknesses.append("Your strategy wins often but has large drawdowns — winners may be too small vs losers.")
        if bc.get("beat_benchmark") is False:
            alpha = bc.get("alpha", 0)
            weaknesses.append(f"Your strategy performs worse than holding the stock (underperforms by {abs(alpha):.1f}%).")
        if total_trades == 0:
            weaknesses.append("No trades were generated — rules may be too strict or conflicting.")
        if total_trades > 50:
            weaknesses.append("Very high trade count — overtrading erodes returns after commissions.")
        if win_rate < 40 and total_trades >= 5:
            weaknesses.append(f"Low win rate ({win_rate:.0f}%) — reconsider entry filters.")

        if drawdown > 10:
            risks.append(f"Maximum drawdown of {drawdown:.1f}% exceeds prudent 10% threshold.")
        if not strategy.get("stop_loss"):
            risks.append("No stop loss defined — a single bad trade could devastate the account.")
        indicators = {r.get("indicator") for r in rules}
        if len(indicators) == 1:
            risks.append("Single-indicator strategy — vulnerable when that indicator fails in current regime.")

        if drawdown > 8:
            suggestions.append("Add or tighten stop-loss rules (1-2% per trade).")
        if bc.get("beat_benchmark") is False:
            suggestions.append("Consider adding a trend filter (e.g., only buy when price is above 200-day MA).")
        if total_trades < 3:
            suggestions.append("Relax entry conditions or test on a longer historical period.")
        if "RSI" not in indicators and "SMA" in indicators:
            suggestions.append("Add RSI filter to avoid buying in overbought conditions.")
        suggestions.append("Compare against library templates in the Strategy Lab before going live.")

        difficulty = self._strategy_difficulty(rules, backtest_results)

        if not strengths:
            strengths.append("Strategy is a learning starting point — iterate based on backtest feedback.")
        if not weaknesses:
            weaknesses.append("No major weaknesses detected — validate on different time periods.")

        return {
            "strategy_name": name,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "risks": risks,
            "improvement_suggestions": suggestions,
            "difficulty_level": difficulty,
        }

    def _strategy_difficulty(self, rules: List[Dict[str, Any]], backtest: Dict[str, Any]) -> str:
        indicators = {r.get("indicator", "") for r in rules}
        if len(indicators) >= 3 or "MACD" in indicators:
            return "advanced"
        if len(rules) >= 2 or "VOLATILITY" in indicators:
            return "intermediate"
        if backtest.get("total_trades", 0) < 3:
            return "beginner (needs more data)"
        return "beginner"
