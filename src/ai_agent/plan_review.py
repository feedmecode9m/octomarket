"""Rule-based trade plan review for educational coaching."""

from typing import Any, Dict, List, Optional


def _grade_from_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def review_pre_trade(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-trade mentor review from structured market context.

    Does not recommend buy/sell — provides observations, warnings, and questions.
    """
    observations: List[str] = []
    warnings: List[str] = []
    questions: List[str] = []
    risk_notes: List[str] = []
    score = 70

    plan = context.get("trade_plan") or {}
    price = context.get("price")
    indicators = context.get("indicators") or {}
    drawings = context.get("drawings") or []
    direction = (plan.get("direction") or "LONG").upper()
    entry = plan.get("entry")
    stop = plan.get("stop")
    target = plan.get("target")
    rr = plan.get("rr")
    thesis = (plan.get("thesis") or "").strip()

    if not plan:
        return {
            "grade": "F",
            "observations": [],
            "warnings": ["No trade plan provided for review."],
            "questions": ["What is your thesis before entering this trade?"],
            "risk_notes": [],
            "review_type": "pre_trade",
        }

    if thesis:
        observations.append(f"Thesis recorded: \"{thesis[:120]}\"")
        score += 5
    else:
        warnings.append("No market thesis documented — define why this trade exists.")
        questions.append("What market structure supports this idea?")
        score -= 10

    resistance_levels = [
        d["price"] for d in drawings
        if d.get("price") is not None and d.get("role") in ("resistance", "level")
    ]
    support_levels = [
        d.get("bottom") or d.get("price") for d in drawings
        if d.get("role") in ("support", "demand", "zone") and (d.get("bottom") or d.get("price"))
    ]

    if entry and resistance_levels:
        nearest_res = min(resistance_levels, key=lambda p: abs(p - entry))
        if abs(entry - nearest_res) / entry < 0.01:
            observations.append("Entry aligns with a drawn resistance/level on the chart.")
            if direction == "LONG":
                questions.append("What confirms the breakout above this level?")
        elif entry > nearest_res and direction == "LONG":
            observations.append("Planned entry is above a marked resistance — breakout setup.")
            score += 5

    entry_source = (plan.get("entry_source") or {})
    if entry_source.get("type") == "drawing":
        observations.append(
            f"Entry price linked to chart drawing #{str(entry_source.get('id', ''))[:8]}."
        )
        score += 5

    rsi = indicators.get("RSI")
    if rsi is not None:
        if rsi >= 70:
            warnings.append(f"RSI is elevated ({rsi}) — momentum may be stretched.")
            score -= 5
        elif rsi <= 30:
            observations.append(f"RSI is low ({rsi}) — potential mean-reversion context.")
        else:
            observations.append(f"RSI is {rsi} — elevated but not extreme.")

    sma20 = indicators.get("SMA20")
    if sma20 is not None and price is not None:
        if price > sma20:
            observations.append("Price is above SMA20 — short-term trend supportive for longs.")
        else:
            observations.append("Price is below SMA20 — short-term trend less supportive for longs.")
            if direction == "LONG":
                warnings.append("Long plan while price is below SMA20 — confirm reversal thesis.")

    macd = indicators.get("MACD")
    if macd == "bullish crossover" and direction == "LONG":
        observations.append("MACD shows bullish crossover — aligns with long direction.")
        score += 5
    elif macd == "bearish crossover" and direction == "LONG":
        warnings.append("MACD bearish crossover conflicts with long plan.")

    if stop and entry:
        stop_dist_pct = abs(entry - stop) / entry * 100
        if stop_dist_pct < 1.5:
            warnings.append("Stop is close to recent volatility range — may get stopped on noise.")
            score -= 5
        if support_levels:
            nearest_support = min(support_levels, key=lambda p: abs(p - stop))
            if abs(stop - nearest_support) / entry < 0.015:
                observations.append("Stop is placed near a drawn support/demand zone.")

    if rr is not None:
        if rr >= 2:
            risk_notes.append(f"Reward exceeds risk by {rr}:1 — meets common 2:1 guideline.")
            score += 10
        elif rr >= 1.5:
            risk_notes.append(f"Risk/reward is {rr}:1 — acceptable but below ideal 2:1 target.")
        else:
            warnings.append(f"Risk/reward {rr}:1 is below 1.5:1 — reward may not justify risk.")
            score -= 10

    if not indicators:
        questions.append("Which indicators confirm your thesis at plan time?")

    if direction == "SHORT":
        questions.append("For shorts, what invalidation level would prove the thesis wrong?")

    if not questions:
        questions.append("What would invalidate this thesis before target is reached?")

    return {
        "grade": _grade_from_score(max(0, min(100, score))),
        "observations": observations,
        "warnings": warnings,
        "questions": questions,
        "risk_notes": risk_notes,
        "review_type": "pre_trade",
        "context_summary": {
            "symbol": context.get("symbol"),
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr": rr,
        },
    }


def review_post_trade(
    context: Dict[str, Any],
    execution: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare planned trade vs actual execution for journal-style coaching."""
    pre = review_pre_trade(context)
    observations = list(pre.get("observations") or [])
    warnings = list(pre.get("warnings") or [])
    questions: List[str] = []
    risk_notes = list(pre.get("risk_notes") or [])
    score = 65

    plan = context.get("trade_plan") or {}
    planned_entry = plan.get("entry")
    planned_target = plan.get("target")
    planned_stop = plan.get("stop")

    fill_price = execution.get("fill_price") or execution.get("entry_price")
    exit_price = execution.get("exit_price")
    pnl = execution.get("pnl")

    if planned_entry and fill_price:
        slip = fill_price - planned_entry
        if abs(slip) / planned_entry < 0.005:
            observations.append(f"Fill ({fill_price}) closely matched planned entry ({planned_entry}).")
            score += 10
        elif slip > 0:
            warnings.append(f"Filled above plan entry ({fill_price} vs {planned_entry}) — slippage on long.")
            score -= 5
        else:
            observations.append(f"Filled below planned entry — better price than planned.")

    if exit_price and planned_target:
        if abs(exit_price - planned_target) / planned_target < 0.02:
            observations.append("Exit near planned target — plan discipline observed.")
            score += 10
        elif (plan.get("direction") or "LONG") == "LONG" and exit_price < planned_target:
            questions.append("Exit was before target — was the thesis invalidated early?")

    if pnl is not None:
        if pnl >= 0:
            observations.append(f"Trade closed profitable (${pnl:.2f}).")
            score += 5
        else:
            observations.append(f"Trade closed at a loss (${pnl:.2f}) — review plan vs outcome.")
            questions.append("Did price action invalidate your thesis before stop?")

    if planned_stop and fill_price and exit_price:
        if (plan.get("direction") or "LONG") == "LONG" and exit_price <= planned_stop * 1.01:
            observations.append("Exit occurred near planned stop — risk plan was tested.")

    questions.append("Did you follow the plan, or did emotion change the exit?")

    return {
        "grade": _grade_from_score(max(0, min(100, score))),
        "observations": observations,
        "warnings": warnings,
        "questions": questions,
        "risk_notes": risk_notes,
        "review_type": "post_trade",
        "plan_vs_actual": {
            "planned_entry": planned_entry,
            "actual_entry": fill_price,
            "planned_target": planned_target,
            "actual_exit": exit_price,
            "pnl": pnl,
        },
        "followed_plan": (
            planned_entry is not None
            and fill_price is not None
            and abs(fill_price - planned_entry) / max(planned_entry, 1) < 0.01
        ),
    }
