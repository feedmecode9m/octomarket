"""Adaptive mentor API — profile, mistakes, scenarios, progress."""

from flask import Blueprint, jsonify, request

from ..ai_agent.mentor import get_trading_mentor
from ..learning.mistake_detector import MistakeDetector
from ..learning.progress import get_progress_tracker
from ..learning.recommendations import AdaptiveRecommendations
from ..learning.skill_score import SkillScoreCalculator
from ..learning.trader_profile import get_trader_profile
from ..models.state import get_simulator_state
from ..simulation.paper_portfolio import get_paper_portfolio
from ..simulation.scenarios import get_scenario_trainer

mentor_bp = Blueprint("mentor", __name__, url_prefix="/api")

_profile = get_trader_profile()
_mentor = get_trading_mentor()
_mistakes = MistakeDetector()
_recommendations = AdaptiveRecommendations()
_progress = get_progress_tracker()
_scenarios = get_scenario_trainer()
_skill_calc = SkillScoreCalculator()
_simulator_state = get_simulator_state()
_portfolio = get_paper_portfolio()


def _get_trades_and_performance():
    from .simulation_routes import get_performance, _portfolio_value_history

    trades = [
        {"type": t.action, "price": t.fill_price, "quantity": t.quantity, "time": t.timestamp}
        for t in _portfolio.trade_history
    ]
    if not trades:
        trades = _simulator_state.trades_list

    perf = get_performance().get_json()
    values = _portfolio_value_history or _simulator_state.portfolio_values
    initial = _portfolio.initial_cash or _simulator_state.global_initial_cash
    return trades, perf, values, initial


def _get_skill_score(trades, perf):
    from ..learning.challenges import get_all_challenges
    return _skill_calc.calculate(
        performance=perf,
        challenge_progress=get_all_challenges(),
        trade_history=trades,
    )


@mentor_bp.route("/profile", methods=["GET"])
def get_profile():
    return jsonify(_profile.get())


@mentor_bp.route("/profile", methods=["POST"])
def update_profile():
    data = request.get_json(silent=True) or {}
    result = _profile.update(data)
    return jsonify(result)


@mentor_bp.route("/mistakes", methods=["GET"])
def get_mistakes():
    trades, perf, values, initial = _get_trades_and_performance()
    detected = _mistakes.analyze(trades, values, initial, perf)
    _profile.set_mistakes([m["mistake"] for m in detected])
    return jsonify({"mistakes": detected})


@mentor_bp.route("/recommendations", methods=["GET"])
def get_recommendations():
    trades, perf, values, initial = _get_trades_and_performance()
    detected = _mistakes.analyze(trades, values, initial, perf)
    recs = _recommendations.recommend(detected, _profile.get())
    return jsonify(recs)


@mentor_bp.route("/mentor/advice", methods=["GET"])
def mentor_advice():
    trades, perf, values, initial = _get_trades_and_performance()
    skill = _get_skill_score(trades, perf)
    detected = _mistakes.analyze(trades, values, initial, perf)
    _profile.record_skill_score(skill["score"], skill["level"])
    _profile.infer_strengths_weaknesses(skill["components"], detected)
    _progress.record_skill_change(skill["score"], skill["level"], skill["components"])

    advice = _mentor.get_advice(trades, _profile.get(), skill, perf, values, initial)
    return jsonify(advice)


@mentor_bp.route("/mentor/ask", methods=["POST"])
def mentor_ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "question is required"}), 400

    trades, perf, values, initial = _get_trades_and_performance()
    skill = _get_skill_score(trades, perf)

    result = _mentor.ask(
        question, trades, _profile.get(), skill, perf, values, initial,
        strategies=data.get("strategies"),
    )
    _progress.record_activity("mentor_question", {"question": question})
    return jsonify(result)


@mentor_bp.route("/scenarios", methods=["GET"])
def list_scenarios():
    return jsonify({"scenarios": _scenarios.list_scenarios()})


@mentor_bp.route("/scenarios/<int:scenario_id>", methods=["GET"])
def get_scenario(scenario_id):
    scenario = _scenarios.get_scenario(scenario_id)
    if not scenario:
        return jsonify({"error": "Scenario not found"}), 404
    return jsonify(scenario)


@mentor_bp.route("/scenarios/<int:scenario_id>/answer", methods=["POST"])
def answer_scenario(scenario_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if not action:
        return jsonify({"error": "action is required"}), 400

    result = _scenarios.score_answer(scenario_id, action, data.get("reasoning", ""))
    if "error" in result:
        return jsonify(result), 404

    _progress.record_activity("scenario_completed", {"scenario_id": scenario_id, "score": result["overall_score"]})
    return jsonify(result)


@mentor_bp.route("/progress", methods=["GET"])
def get_progress():
    return jsonify(_progress.get_progress())
