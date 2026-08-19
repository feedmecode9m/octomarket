"""Simulation, replay, portfolio, performance, and challenge API routes."""

import threading
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..analytics.performance import TradingPerformanceAnalytics
from ..learning.challenges import get_all_challenges, get_challenge_tracker
from ..learning.skill_score import SkillScoreCalculator
from ..models.state import get_simulator_state
from ..replay.replay_session import get_replay_session
from ..simulation.paper_portfolio import get_paper_portfolio

simulation_bp = Blueprint("simulation", __name__, url_prefix="/api")

_replay = get_replay_session()
_portfolio = get_paper_portfolio()
_analytics = TradingPerformanceAnalytics()
_challenges = get_challenge_tracker()
_simulator_state = get_simulator_state()

_portfolio_value_history: list = []
_benchmark_price: float = 0.0
_last_backtest_cache: dict = {}
_skill_calc = SkillScoreCalculator()


def _record_portfolio_snapshot(prices: dict):
    global _portfolio_value_history
    value = _portfolio.get_portfolio_value(prices)
    _portfolio_value_history.append(value)
    if len(_portfolio_value_history) > 500:
        _portfolio_value_history.pop(0)


# --- Market Replay (legacy shim → canonical ReplaySessionManager) ---


def _legacy_replay_status() -> dict:
    state = _replay.get_state()
    speed_raw = state.get("speed") or "1x"
    speed_num = 1
    if isinstance(speed_raw, str) and speed_raw.endswith("x"):
        try:
            speed_num = int(speed_raw[:-1])
        except ValueError:
            speed_num = 1
    return {
        "symbol": state.get("symbol"),
        "total_candles": state.get("total_candles", 0),
        "current_index": state.get("current_index", -1),
        "progress_pct": state.get("progress_pct", 0),
        "is_playing": False,
        "speed": speed_num,
        "at_end": state.get("status") == "completed",
        "current_candle": state.get("current_candle"),
    }


@simulation_bp.route("/simulation/replay/load", methods=["POST"])
def replay_load():
    """Load OHLCV data for replay mode (delegates to /api/replay/start)."""
    global _benchmark_price, _portfolio_value_history
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "AAPL")
    interval = data.get("interval", "1d")
    period = data.get("period", "5d")
    initial_cash = float(data.get("initial_cash", 10000))

    state = _replay.start(
        instrument_id=symbol,
        period=period,
        interval=interval,
        initial_cash=initial_cash,
        reset_portfolio=True,
    )
    count = state.get("total_candles", 0)
    _portfolio.reset(initial_cash)
    _portfolio_value_history = [initial_cash]
    candle = state.get("current_candle")
    _benchmark_price = float(candle["close"]) if candle else 0.0

    return jsonify({
        "message": "Replay loaded",
        "symbol": state.get("symbol") or symbol.upper(),
        "candles": count,
        "initial_cash": initial_cash,
    })


@simulation_bp.route("/simulation/replay/status", methods=["GET"])
def replay_status():
    status = _legacy_replay_status()
    candle = status.get("current_candle")
    prices = {}
    if candle and status.get("symbol"):
        prices[status["symbol"]] = candle.get("close", candle.get("close"))
    status["portfolio"] = _portfolio.to_dict(prices)
    return jsonify(status)


@simulation_bp.route("/simulation/replay/step", methods=["POST"])
def replay_step():
    state = _replay.step()
    candle = state.get("current_candle")
    if not candle and state.get("status") == "completed":
        return jsonify({"message": "End of data", "status": _legacy_replay_status()}), 200

    if candle and state.get("symbol"):
        prices = {state["symbol"]: candle.get("close", 0)}
        _record_portfolio_snapshot(prices)

    return jsonify({"candle": candle, "status": _legacy_replay_status()})


@simulation_bp.route("/simulation/replay/play", methods=["POST"])
def replay_play():
    return jsonify({
        "message": "Auto-play is not supported; use step endpoint",
        "status": _legacy_replay_status(),
    })


@simulation_bp.route("/simulation/replay/pause", methods=["POST"])
def replay_pause():
    return jsonify({"message": "Replay paused", "status": _replay.pause()})


@simulation_bp.route("/simulation/replay/speed", methods=["POST"])
def replay_speed():
    data = request.get_json(silent=True) or {}
    speed = data.get("speed", 1)
    state = _replay.set_speed(f"{speed}x")
    return jsonify({"speed": speed, "status": state})


@simulation_bp.route("/simulation/replay/reset", methods=["POST"])
def replay_reset():
    return jsonify({"message": "Replay reset", "status": _replay.reset()})


# --- Manual Trading ---

@simulation_bp.route("/simulation/trade", methods=["POST"])
def manual_trade():
    """Execute manual BUY, SELL, or HOLD during replay."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").upper()
    symbol = data.get("symbol") or _replay.get_state().get("symbol", "AAPL")
    reason = data.get("reason", "")
    quantity = int(data.get("quantity", 0))

    state = _replay.get_state()
    candle = state.get("current_candle")
    if not candle and action != "HOLD":
        return jsonify({"error": "No active candle — load replay and step first"}), 400

    price = candle.get("close", 0) if candle else 0
    ts = candle.get("timestamp") if candle else datetime.now().isoformat()

    if action == "HOLD":
        result = _portfolio.hold(symbol, reason)
    elif action == "BUY":
        if quantity <= 0:
            quantity = max(1, int(_portfolio.cash * 0.1 / price)) if price > 0 else 1
        result = _portfolio.buy(symbol, price, quantity, ts, reason)
    elif action == "SELL":
        result = _portfolio.sell(symbol, price, quantity or None, ts, reason)
    else:
        return jsonify({"error": "action must be BUY, SELL, or HOLD"}), 400

    if candle:
        _record_portfolio_snapshot({symbol: price})

    return jsonify({**result, "portfolio": _portfolio.to_dict({symbol: price})})


@simulation_bp.route("/simulation/portfolio", methods=["GET"])
def get_portfolio():
    status = _replay.get_state()
    symbol = status.get("symbol", "")
    prices = {}
    candle = status.get("current_candle")
    if candle and symbol:
        prices[symbol] = candle.get("close", 0)
    return jsonify(_portfolio.to_dict(prices))


# --- Performance Analytics ---

@simulation_bp.route("/performance", methods=["GET"])
def get_performance():
    """Comprehensive trading performance analytics."""
    status = _replay.get_state()
    symbol = status.get("symbol", "")

    trades = [
        {
            "type": t.action,
            "price": t.fill_price,
            "quantity": t.quantity,
            "time": t.timestamp,
            "symbol": t.symbol,
        }
        for t in _portfolio.trade_history
    ]

    if not trades:
        trades = _simulator_state.trades_list

    values = _portfolio_value_history or _simulator_state.portfolio_values
    initial = _portfolio.initial_cash or _simulator_state.global_initial_cash

    benchmark_return = None
    candle = status.get("current_candle")
    if _benchmark_price > 0 and candle:
        benchmark_return = (candle.get("close", 0) - _benchmark_price) / _benchmark_price * 100

    metrics = _analytics.calculate(
        trades=trades,
        portfolio_values=values,
        initial_cash=initial,
        benchmark_return_pct=benchmark_return,
    )

    return jsonify(metrics)


# --- Challenges ---

@simulation_bp.route("/challenges", methods=["GET"])
def list_challenges():
    return jsonify({"challenges": get_all_challenges()})


@simulation_bp.route("/challenges/<int:challenge_id>", methods=["GET"])
def get_challenge(challenge_id):
    challenge = _challenges.get_challenge(challenge_id)
    if not challenge:
        return jsonify({"error": "Challenge not found"}), 404
    return jsonify(challenge)


@simulation_bp.route("/challenges/<int:challenge_id>/evaluate", methods=["POST"])
def evaluate_challenge(challenge_id):
    perf_resp = get_performance()
    metrics = perf_resp.get_json()
    result = _challenges.evaluate(challenge_id, metrics)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@simulation_bp.route("/simulation/journal-timeline", methods=["GET"])
def journal_timeline():
    """Chronological timeline of trades and position changes."""
    entries = []
    for record in _portfolio.position_history:
        entries.append({
            "type": "trade",
            "timestamp": record["timestamp"],
            "action": record["action"],
            "symbol": record["symbol"],
            "quantity": record["quantity"],
            "price": record["fill_price"],
            "pnl": record.get("realized_pnl", 0),
            "cash_after": record["cash_after"],
        })

    for trade in _simulator_state.trades_list:
        entries.append({
            "type": "auto_trade",
            "timestamp": trade.get("time", ""),
            "action": trade.get("type", ""),
            "symbol": trade.get("symbol", ""),
            "quantity": trade.get("quantity", 0),
            "price": trade.get("price", 0),
        })

    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return jsonify({"timeline": entries})


@simulation_bp.route("/skill-score", methods=["GET"])
def get_skill_score():
    """Trading skill rating 0-100."""
    perf = get_performance().get_json()
    result = _skill_calc.calculate(
        performance=perf,
        backtest_results=_last_backtest_cache,
        challenge_progress=get_all_challenges(),
        trade_history=_simulator_state.trades_list,
    )
    return jsonify(result)


def set_last_backtest_result(result: dict):
    """Allow strategy lab to share backtest results for skill scoring."""
    global _last_backtest_cache
    _last_backtest_cache = result
