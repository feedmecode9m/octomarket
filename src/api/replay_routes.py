"""Canonical replay API — instrument-aware session control."""

from flask import Blueprint, jsonify, request

from ..replay.comparison import compare_plan_to_outcome
from ..replay.replay_memory import get_replay_memory
from ..replay.replay_session import get_replay_session
from ..trading.trade_plan import get_trade_plan_manager

replay_bp = Blueprint("replay", __name__, url_prefix="/api/replay")

_replay = get_replay_session()
_plans = get_trade_plan_manager()
_memory = get_replay_memory()


@replay_bp.route("/start", methods=["POST"])
def replay_start():
    data = request.get_json(silent=True) or {}
    instrument_id = data.get("instrument_id") or data.get("symbol")
    if not instrument_id:
        return jsonify({"error": "instrument_id or symbol is required"}), 400
    try:
        if data.get("record_id"):
            state = _replay.start_from_record(
                data["record_id"],
                initial_cash=float(data.get("initial_cash", 10000)),
                reset_portfolio=data.get("reset_portfolio", True),
            )
        else:
            state = _replay.start(
                instrument_id=instrument_id,
                period=data.get("period", "1mo"),
                interval=data.get("interval", "1d"),
                initial_cash=float(data.get("initial_cash", 10000)),
                reset_portfolio=data.get("reset_portfolio", True),
            )
        return jsonify({"message": "Replay started", "state": state})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@replay_bp.route("/step", methods=["POST"])
def replay_step():
    state = _replay.step()
    if state.get("error"):
        return jsonify(state), 400
    return jsonify(state)


@replay_bp.route("/state", methods=["GET"])
def replay_state():
    instrument_id = request.args.get("instrument_id") or request.args.get("symbol")
    state = _replay.get_state()
    if instrument_id or _replay.is_active():
        state["visible_candles"] = _replay.get_visible_candles(instrument_id)
    return jsonify(state)


@replay_bp.route("/candles/<instrument_id>", methods=["GET"])
def replay_candles(instrument_id):
    """Visible candles only — no future leakage."""
    if not _replay.is_active():
        return jsonify({"error": "No active replay session"}), 400
    return jsonify(_replay.get_visible_candles(instrument_id))


@replay_bp.route("/pause", methods=["POST"])
def replay_pause():
    return jsonify(_replay.pause())


@replay_bp.route("/resume", methods=["POST"])
def replay_resume():
    return jsonify(_replay.resume())


@replay_bp.route("/reset", methods=["POST"])
def replay_reset():
    return jsonify(_replay.reset())


@replay_bp.route("/speed", methods=["POST"])
def replay_speed():
    data = request.get_json(silent=True) or {}
    return jsonify(_replay.set_speed(data.get("speed", "1x")))


@replay_bp.route("/mode", methods=["GET", "POST"])
def replay_mode():
    if request.method == "GET":
        return jsonify(_replay.get_state())
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(_replay.set_mode(data.get("mode", "live")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@replay_bp.route("/compare", methods=["POST"])
def replay_compare():
    """Compare trade plan vs replay session metrics and optional stored outcome."""
    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")
    plan = data.get("trade_plan")
    if plan_id:
        plan = _plans.get_plan(plan_id)
    if not plan:
        return jsonify({"error": "trade_plan or plan_id required"}), 400

    metrics = data.get("metrics") or _replay.get_state().get("metrics")
    execution = dict(data.get("execution") or {})

    record = _memory.get_by_plan_id(plan.get("id")) if plan.get("id") else None
    if record:
        stored_execution = record.get("execution") or {}
        stored_outcome = record.get("outcome") or {}
        exit_payload = stored_execution.get("exit") or {}
        if exit_payload.get("price") is not None:
            execution.setdefault("exit_price", exit_payload["price"])
        if stored_outcome.get("pnl") is not None:
            execution.setdefault("pnl", stored_outcome["pnl"])
        execution.setdefault("record_id", record.get("id"))
        execution.setdefault("record_status", record.get("status"))

    comparison = compare_plan_to_outcome(plan, metrics, execution)
    return jsonify({
        "comparison": comparison,
        "metrics": metrics,
        "execution": execution,
        "record": record,
    })
