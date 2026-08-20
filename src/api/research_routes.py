"""Strategy research API — evaluate strategies via ReplayRecord pipeline."""

from flask import Blueprint, jsonify, request

from ..research.runner import get_strategy_backtest_runner
from ..research.selection import get_adaptive_strategy_selector, preferred_strategy_from_recommendation
from ..research.store import get_research_report_store
from ..research.validation import get_strategy_validation_service
from ..research.walkforward import get_walk_forward_service
from ..strategies.engine import get_strategy_engine
from ..strategies.registry import get_strategy_registry

research_bp = Blueprint("research", __name__, url_prefix="/api/research")

_registry = get_strategy_registry()
_runner = get_strategy_backtest_runner()
_validator = get_strategy_validation_service()
_walkforward = get_walk_forward_service()
_selector = get_adaptive_strategy_selector()
_engine = get_strategy_engine()
_reports = get_research_report_store()


@research_bp.route("/strategies", methods=["GET"])
def research_strategies():
    """List strategies available for research evaluation."""
    return jsonify({"catalog": _registry.catalog(), "strategies": _registry.list_all()})


@research_bp.route("/run", methods=["POST"])
def research_run():
    """Run strategy evaluation through replay lifecycle and return StrategyReport."""
    data = request.get_json(silent=True) or {}
    strategy_id = data.get("strategy_id")
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not strategy_id or not instrument_id:
        return jsonify({"error": "strategy_id and instrument_id are required"}), 400

    try:
        report = _runner.run(
            strategy_id,
            instrument_id,
            period=data.get("period", "6mo"),
            interval=data.get("interval", "1d"),
            initial_cash=float(data.get("initial_cash", 10000)),
            cooldown_bars=int(data.get("cooldown_bars", 1)),
            max_trades=data.get("max_trades"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )
        return jsonify({"report": report}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@research_bp.route("/report/<report_id>", methods=["GET"])
def research_report(report_id):
    """Fetch a stored strategy research report by id or latest for strategy query."""
    strategy_id = request.args.get("strategy_id")
    instrument_id = request.args.get("instrument_id")

    if report_id == "latest" and strategy_id:
        report = _reports.latest_for_strategy(strategy_id, instrument_id=instrument_id)
    else:
        report = _reports.get(report_id)
        if not report and strategy_id:
            report = _reports.latest_for_strategy(strategy_id, instrument_id=instrument_id)

    if not report:
        return jsonify({"error": "Research report not found"}), 404
    return jsonify({"report": report})


@research_bp.route("/validate", methods=["POST"])
def research_validate():
    """Run all compatible strategies under identical conditions and compare."""
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400
    try:
        comparison = _validator.run_batch(
            instrument_id,
            period=data.get("period", "6mo"),
            interval=data.get("interval", "1d"),
            initial_cash=float(data.get("initial_cash", 10000)),
            cooldown_bars=int(data.get("cooldown_bars", 1)),
            max_trades=data.get("max_trades"),
            strategy_ids=data.get("strategy_ids"),
        )
        return jsonify({"comparison": comparison}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@research_bp.route("/compare/<comparison_id>", methods=["GET"])
def research_compare(comparison_id):
    """Fetch a stored strategy comparison report."""
    if comparison_id == "latest":
        instrument_id = request.args.get("instrument_id")
        if not instrument_id:
            return jsonify({"error": "instrument_id required for latest comparison"}), 400
        report = _reports.latest_comparison(
            instrument_id,
            period=request.args.get("period"),
        )
    else:
        report = _reports.get(comparison_id)
    if not report or report.get("report_type") != "comparison":
        return jsonify({"error": "Comparison report not found"}), 404
    return jsonify({"comparison": report})


@research_bp.route("/walkforward", methods=["POST"])
def research_walkforward():
    """Run walk-forward evaluation across research / validation / OOS windows."""
    data = request.get_json(silent=True) or {}
    strategy_id = data.get("strategy_id")
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not strategy_id or not instrument_id:
        return jsonify({"error": "strategy_id and instrument_id are required"}), 400
    try:
        report = _walkforward.run(
            strategy_id,
            instrument_id,
            period=data.get("period", "2y"),
            interval=data.get("interval", "1d"),
            initial_cash=float(data.get("initial_cash", 10000)),
            cooldown_bars=int(data.get("cooldown_bars", 1)),
            max_trades=data.get("max_trades"),
            windows=data.get("windows"),
            research_ratio=float(data.get("research_ratio", 0.5)),
            validation_ratio=float(data.get("validation_ratio", 0.25)),
            out_of_sample_ratio=float(data.get("out_of_sample_ratio", 0.25)),
        )
        return jsonify({"walk_forward": report}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@research_bp.route("/walkforward/<walk_forward_id>", methods=["GET"])
def research_walkforward_get(walk_forward_id):
    if walk_forward_id == "latest":
        strategy_id = request.args.get("strategy_id")
        instrument_id = request.args.get("instrument_id")
        if not strategy_id or not instrument_id:
            return jsonify({"error": "strategy_id and instrument_id required for latest"}), 400
        reports = [
            r for r in _reports.list_all()
            if r.get("report_type") == "walk_forward"
            and r.get("strategy_id") == strategy_id
            and r.get("instrument_id") == instrument_id
        ]
        report = reports[-1] if reports else None
    else:
        report = _reports.get(walk_forward_id)
    if not report or report.get("report_type") != "walk_forward":
        return jsonify({"error": "Walk-forward report not found"}), 404
    return jsonify({"walk_forward": report})


@research_bp.route("/recommend", methods=["POST"])
def research_recommend():
    """Recommend a strategy family from current context and stored research. Decision support only."""
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400
    try:
        payload = _selector.recommend(
            instrument_id,
            timeframe=data.get("timeframe") or data.get("interval") or "1d",
            period=data.get("period", "3mo"),
            min_trades=int(data.get("min_trades", 10)),
            require_cost_adjusted_edge=bool(data.get("require_cost_adjusted_edge", True)),
        )
        # 17B: attach read-only trader history context — never alters ranking or execution.
        try:
            from ..learning.journal_analytics import get_journal_analytics_service

            rec = payload.get("recommendation") or {}
            payload["trader_history_context"] = get_journal_analytics_service().recommendation_context(
                instrument_id=payload.get("instrument_id") or instrument_id,
                strategy_family=rec.get("strategy_family"),
                min_trades=5,
            )
        except Exception:
            payload["trader_history_context"] = {
                "decision_support_only": True,
                "read_only": True,
                "trader_history": {"alignment": "insufficient", "narrative": "Journal context unavailable."},
            }
        return jsonify({"recommendation": payload})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@research_bp.route("/recommend/create-plan", methods=["POST"])
def research_recommend_create_plan():
    """
    Human approval bridge: recommendation → StrategyEngine → TradePlanManager.

    Does not create orders, execute fills, or mutate ReplayRecords directly.
    """
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400

    strategy_id = data.get("strategy_id")
    if not strategy_id:
        strategy_id = preferred_strategy_from_recommendation(data.get("recommendation") or data)
    if not strategy_id:
        return jsonify({"error": "No strategy available to create a plan from this recommendation"}), 400

    try:
        result = _engine.generate_plan(
            strategy_id,
            instrument_id,
            timeframe=data.get("timeframe") or data.get("interval"),
            period=data.get("period"),
            account_balance=data.get("account_balance"),
            risk_percent=data.get("risk_percent"),
        )
        result["decision_support_only"] = True
        result["created_from_recommendation"] = True
        if not result.get("plan"):
            return jsonify(result), 200
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@research_bp.route("/reports", methods=["GET"])
def research_reports_list():
    return jsonify({"reports": _reports.list_all()})
