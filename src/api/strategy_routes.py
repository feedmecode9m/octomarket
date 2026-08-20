"""Strategy engine API — catalog, evaluation, and TradePlan generation."""

from flask import Blueprint, jsonify, request

from ..strategies.engine import get_strategy_engine
from ..strategies.registry import get_strategy_registry

strategy_bp = Blueprint("strategies", __name__, url_prefix="/api/strategies")

_registry = get_strategy_registry()
_engine = get_strategy_engine()


@strategy_bp.route("", methods=["GET"])
def list_strategies():
    """Return strategy catalog grouped by asset class."""
    asset_class = request.args.get("asset_class")
    if asset_class:
        return jsonify({
            "asset_class": asset_class.upper(),
            "strategies": _registry.list_by_asset_class(asset_class),
        })
    return jsonify({"catalog": _registry.catalog(), "strategies": _registry.list_all()})


@strategy_bp.route("/<strategy_id>", methods=["GET"])
def get_strategy(strategy_id):
    strategy = _registry.get(strategy_id)
    if not strategy:
        return jsonify({"error": f"Strategy '{strategy_id}' not found"}), 404
    return jsonify(strategy.metadata())


@strategy_bp.route("/<strategy_id>/evaluate", methods=["POST"])
def evaluate_strategy(strategy_id):
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400
    try:
        result = _engine.evaluate(
            strategy_id,
            instrument_id,
            timeframe=data.get("timeframe"),
            period=data.get("period"),
            account_balance=data.get("account_balance"),
            risk_percent=data.get("risk_percent"),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@strategy_bp.route("/<strategy_id>/generate-plan", methods=["POST"])
def generate_strategy_plan(strategy_id):
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400
    try:
        result = _engine.generate_plan(
            strategy_id,
            instrument_id,
            timeframe=data.get("timeframe"),
            period=data.get("period"),
            account_balance=data.get("account_balance"),
            risk_percent=data.get("risk_percent"),
        )
        if not result.get("plan"):
            return jsonify(result), 200
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
