"""Chart workspace API — state, OHLCV candles, and indicators."""

from flask import Blueprint, jsonify, request

from ..charting.candle_engine import get_candle_engine
from ..charting.chart_state import get_chart_state
from ..charting.drawing_store import get_drawing_store
from ..charting.indicators import compute_indicators_for_candles, parse_indicators_query

chart_bp = Blueprint("chart", __name__, url_prefix="/api/chart")

_state = get_chart_state()
_candles = get_candle_engine()
_drawings = get_drawing_store()


def _workspace_with_drawings() -> dict:
    state = _state.get_state()
    state["drawings"] = _drawings.list_drawings(state["symbol"])
    return state


@chart_bp.route("/state", methods=["GET"])
def get_chart_workspace_state():
    """Return the active chart workspace state."""
    return jsonify(_workspace_with_drawings())


@chart_bp.route("/state", methods=["PUT"])
def update_chart_workspace_state():
    """Update chart workspace (symbol, timeframe, zoom, indicators, drawings)."""
    data = request.get_json(silent=True) or {}
    try:
        updated = _state.update(**data)
        updated["drawings"] = _drawings.list_drawings(updated["symbol"])
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


@chart_bp.route("/<symbol>/drawings", methods=["GET"])
def list_chart_drawings(symbol):
    """Return saved drawings for symbol."""
    symbol = symbol.upper()
    return jsonify(_drawings.list_drawings(symbol))


@chart_bp.route("/<symbol>/drawings", methods=["POST"])
def create_chart_drawing(symbol):
    """Create a drawing for symbol."""
    symbol = symbol.upper()
    data = request.get_json(silent=True) or {}
    try:
        drawing = _drawings.create_drawing(symbol, data)
        workspace = _state.get_state()
        if workspace["symbol"] == symbol:
            _state.update(drawings=_drawings.list_drawings(symbol))
        return jsonify({"message": "Drawing created", "drawing": drawing}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@chart_bp.route("/<symbol>/drawings/<drawing_id>", methods=["PUT"])
def update_chart_drawing(symbol, drawing_id):
    """Update a drawing by id."""
    symbol = symbol.upper()
    data = request.get_json(silent=True) or {}
    try:
        drawing = _drawings.update_drawing(symbol, drawing_id, data)
        workspace = _state.get_state()
        if workspace["symbol"] == symbol:
            _state.update(drawings=_drawings.list_drawings(symbol))
        return jsonify({"message": "Drawing updated", "drawing": drawing})
    except KeyError:
        return jsonify({"error": f"Drawing '{drawing_id}' not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@chart_bp.route("/<symbol>/drawings/<drawing_id>", methods=["DELETE"])
def delete_chart_drawing(symbol, drawing_id):
    """Delete a drawing by id."""
    symbol = symbol.upper()
    if not _drawings.delete_drawing(symbol, drawing_id):
        return jsonify({"error": f"Drawing '{drawing_id}' not found"}), 404
    workspace = _state.get_state()
    if workspace["symbol"] == symbol:
        _state.update(drawings=_drawings.list_drawings(symbol))
    return jsonify({"message": "Drawing deleted", "id": drawing_id})


@chart_bp.route("/<symbol>/indicators", methods=["GET"])
def get_chart_indicators(symbol):
    """
    Return computed technical indicators for symbol.

    Query: indicators=SMA20,EMA9,RSI,MACD,BB (comma-separated)
    """
    symbol = symbol.upper()
    workspace = _state.get_state()

    indicator_query = request.args.get("indicators", "")
    if not indicator_query.strip():
        return jsonify({"error": "Query param 'indicators' is required (e.g. SMA20,RSI,MACD)"}), 400

    try:
        parse_indicators_query(indicator_query)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    interval = request.args.get("timeframe") or request.args.get("interval") or workspace["timeframe"]
    period = request.args.get("period") or workspace["period"]
    respect_session = request.args.get("respect_session", "true").lower() != "false"

    try:
        candle_payload = _candles.get_candles(
            symbol=symbol,
            interval=interval,
            period=period,
            respect_session=respect_session,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if candle_payload["count"] == 0:
        return jsonify({"error": f"No candle data for {symbol}"}), 404

    try:
        payload = compute_indicators_for_candles(candle_payload, indicator_query)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(payload)
