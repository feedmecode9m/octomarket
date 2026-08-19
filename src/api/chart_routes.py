"""Chart workspace API — state and OHLCV candles."""

from flask import Blueprint, jsonify, request

from ..charting.candle_engine import get_candle_engine
from ..charting.chart_state import get_chart_state

chart_bp = Blueprint("chart", __name__, url_prefix="/api/chart")

_state = get_chart_state()
_candles = get_candle_engine()


@chart_bp.route("/state", methods=["GET"])
def get_chart_workspace_state():
    """Return the active chart workspace state."""
    return jsonify(_state.get_state())


@chart_bp.route("/state", methods=["PUT"])
def update_chart_workspace_state():
    """Update chart workspace (symbol, timeframe, zoom, indicators, drawings)."""
    data = request.get_json(silent=True) or {}
    try:
        updated = _state.update(**data)
        return jsonify({"message": "Chart state updated", "state": updated})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@chart_bp.route("/<symbol>", methods=["GET"])
def get_chart_candles(symbol):
    """
    Return OHLCV candles for symbol.

    Uses workspace timeframe/period unless overridden via query params.
    Session-aware: no future candles beyond current session index.
    """
    symbol = symbol.upper()
    workspace = _state.get_state()

    interval = request.args.get("timeframe") or request.args.get("interval") or workspace["timeframe"]
    period = request.args.get("period") or workspace["period"]
    respect_session = request.args.get("respect_session", "true").lower() != "false"

    try:
        payload = _candles.get_candles(
            symbol=symbol,
            interval=interval,
            period=period,
            respect_session=respect_session,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if payload["count"] == 0:
        return jsonify({"error": f"No candle data for {symbol}"}), 404

    payload["workspace"] = {
        "symbol": workspace["symbol"],
        "timeframe": workspace["timeframe"],
        "period": workspace["period"],
    }
    return jsonify(payload)
