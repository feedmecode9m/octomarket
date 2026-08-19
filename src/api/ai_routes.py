"""AI Trading Coach API endpoints."""

from flask import Blueprint, jsonify, request

from ..ai_agent.agent import TradingCoachAgent
from ..ai_agent.trade_journal import get_trade_journal
from ..learning.lessons import get_all_lessons, get_lesson_by_id
from ..models.state import get_simulator_state

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

_coach = TradingCoachAgent()
_simulator_state = get_simulator_state()
_journal = get_trade_journal()


@ai_bp.route("/analyze-market", methods=["POST"])
def analyze_market():
    """
    Analyze market state and return educational guidance.

    Input: { symbol, indicators, portfolio }
    Output: { market_summary, possible_scenarios, risk_warning, learning_points, ... }
    """
    try:
        data = request.get_json(silent=True) or {}

        symbol = data.get("symbol")
        if not symbol:
            return jsonify({"error": "symbol is required"}), 400

        indicators = data.get("indicators") or {}
        portfolio = data.get("portfolio") or {}
        prices = data.get("prices")
        strategy = data.get("strategy")

        result = _coach.analyze_market(
            symbol=symbol,
            indicators=indicators,
            portfolio=portfolio,
            prices=prices,
            strategy=strategy,
        )

        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@ai_bp.route("/review-trade", methods=["POST"])
def review_trade():
    """
    Review trade history and provide educational feedback.

    Input: { trade_history, strategy, outcome }
    Output: { mistakes, strengths, improvement_plan }
    """
    try:
        data = request.get_json(silent=True) or {}

        trade_history = data.get("trade_history")
        if trade_history is None:
            trade_history = _simulator_state.trades_list

        strategy = data.get("strategy") or {}
        outcome = data.get("outcome") or {}

        result = _coach.review_trade(
            trade_history=trade_history,
            strategy=strategy,
            outcome=outcome,
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Review failed: {str(e)}"}), 500


@ai_bp.route("/lessons", methods=["GET"])
def list_lessons():
    """List all available learning lessons."""
    return jsonify({"lessons": get_all_lessons()})


@ai_bp.route("/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id: int):
    """Get a single lesson with full content."""
    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        return jsonify({"error": f"Lesson {lesson_id} not found"}), 404
    return jsonify(lesson)


@ai_bp.route("/journal", methods=["GET"])
def get_journal():
    """Get all trade journal entries."""
    return jsonify({
        "entries": _journal.get_all(),
        "summary": _journal.get_summary(),
    })


@ai_bp.route("/journal", methods=["POST"])
def add_journal_entry():
    """Add a manual journal entry."""
    try:
        data = request.get_json(silent=True) or {}

        required = ["symbol", "type", "entry_price", "quantity", "reason"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        entry = _journal.record(
            symbol=data["symbol"],
            trade_type=data["type"],
            entry_price=float(data["entry_price"]),
            quantity=int(data["quantity"]),
            reason=data["reason"],
            exit_price=float(data["exit_price"]) if data.get("exit_price") else None,
            lesson_learned=data.get("lesson_learned"),
            strategy=data.get("strategy"),
        )

        return jsonify(entry), 201

    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@ai_bp.route("/coach-summary", methods=["GET"])
def coach_summary():
    """Get a live coach summary from current simulator state."""
    try:
        symbol = _simulator_state.current_symbol or "AAPL"

        indicators = {}
        if not _simulator_state.current_signals.empty:
            latest = _simulator_state.current_signals.iloc[-1]
            indicators = {
                "rsi": float(latest.get("rsi", 0)) if latest.get("rsi") == latest.get("rsi") else None,
                "short_ma": float(latest.get("short_ma", 0)),
                "long_ma": float(latest.get("long_ma", 0)),
                "price_momentum": float(latest.get("price_momentum", 0)),
                "volatility": float(latest.get("volatility", 0)) if latest.get("volatility") == latest.get("volatility") else None,
                "current_price": float(latest.get("price", 0)),
            }

        portfolio_values = _simulator_state.portfolio_values
        current_value = portfolio_values[-1] if portfolio_values else _simulator_state.global_initial_cash

        portfolio = {
            "cash": _simulator_state.global_initial_cash,
            "current_value": current_value,
            "initial_cash": _simulator_state.global_initial_cash,
            "shares_held": 0,
            "portfolio_values": portfolio_values,
        }

        prices = []
        if not _simulator_state.current_data.empty and "Close" in _simulator_state.current_data.columns:
            prices = _simulator_state.current_data["Close"].tolist()

        market_result = _coach.analyze_market(symbol, indicators, portfolio, prices)
        review_result = _coach.review_trade(
            trade_history=_simulator_state.trades_list,
            outcome={"total_return_pct": 0, "win_rate": 0, "max_drawdown": 0},
        )

        return jsonify({
            **market_result,
            "journal_feedback": review_result.get("journal_feedback", ""),
            "mistakes": review_result.get("mistakes", []),
            "strengths": review_result.get("strengths", []),
            "improvement_plan": review_result.get("improvement_plan", []),
        })

    except Exception as e:
        return jsonify({"error": f"Coach summary failed: {str(e)}"}), 500


@ai_bp.route("/review-strategy", methods=["POST"])
def review_strategy():
    """Review a strategy and its backtest results."""
    try:
        data = request.get_json(silent=True) or {}
        strategy = data.get("strategy")
        backtest_results = data.get("backtest_results")
        if not strategy or not backtest_results:
            return jsonify({"error": "strategy and backtest_results are required"}), 400
        result = _coach.review_strategy(strategy, backtest_results)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/pre-trade-review", methods=["POST"])
def pre_trade_review():
    """Review a planned trade before execution."""
    try:
        data = request.get_json(silent=True) or {}
        action = data.get("action", "BUY")
        symbol = data.get("symbol", "AAPL")
        result = _coach.pre_trade_review(
            action=action,
            symbol=symbol,
            market_state=data.get("market_state", {"indicators": data.get("indicators", {})}),
            portfolio=data.get("portfolio", {}),
            reason=data.get("reason", ""),
            strategy=data.get("strategy"),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/post-trade-review", methods=["POST"])
def post_trade_review():
    """Review a completed trade."""
    try:
        data = request.get_json(silent=True) or {}
        trade = data.get("trade")
        if not trade:
            return jsonify({"error": "trade is required"}), 400
        result = _coach.post_trade_review(trade, data.get("outcome"))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
