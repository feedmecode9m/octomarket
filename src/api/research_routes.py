"""Strategy research API — evaluate strategies via ReplayRecord pipeline."""

from flask import Blueprint, jsonify, request

from ..research.runner import get_strategy_backtest_runner
from ..research.store import get_research_report_store
from ..strategies.registry import get_strategy_registry

research_bp = Blueprint("research", __name__, url_prefix="/api/research")

_registry = get_strategy_registry()
_runner = get_strategy_backtest_runner()
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


@research_bp.route("/reports", methods=["GET"])
def research_reports_list():
    return jsonify({"reports": _reports.list_all()})
