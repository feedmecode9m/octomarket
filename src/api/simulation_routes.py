"""Simulation, replay, portfolio, performance, and challenge API routes."""

import threading
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..analytics.performance import TradingPerformanceAnalytics
from ..core.data_fetcher import DataFetcher
from ..learning.challenges import get_all_challenges, get_challenge_tracker
from ..models.state import get_simulator_state
from ..simulation.market_replay import get_replay_engine
from ..simulation.paper_portfolio import get_paper_portfolio

simulation_bp = Blueprint("simulation", __name__, url_prefix="/api")

_replay = get_replay_engine()
_portfolio = get_paper_portfolio()
_analytics = TradingPerformanceAnalytics()
_challenges = get_challenge_tracker()
_simulator_state = get_simulator_state()

_portfolio_value_history: list = []
_benchmark_price: float = 0.0


def _record_portfolio_snapshot(prices: dict):
    global _portfolio_value_history
    value = _portfolio.get_portfolio_value(prices)
    _portfolio_value_history.append(value)
    if len(_portfolio_value_history) > 500:
        _portfolio_value_history.pop(0)


# --- Market Replay ---

@simulation_bp.route("/simulation/replay/load", methods=["POST"])
def replay_load():
    """Load OHLCV data for replay mode."""
    global _benchmark_price, _portfolio_value_history
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "AAPL")
    interval = data.get("interval", "1m")
    period = data.get("period", "5d")
    start_date = data.get("selected_date")
    initial_cash = float(data.get("initial_cash", 10000))

    fetcher = DataFetcher(symbol=symbol, interval=interval, period=period, start_date=start_date)
    ohlcv = fetcher.get_real_time_data()

    if ohlcv.empty:
        return jsonify({"error": "No data available for replay"}), 404

    count = _replay.load(ohlcv, symbol)
    _portfolio.reset(initial_cash)
    _portfolio_value_history = [initial_cash]
    _benchmark_price = float(ohlcv["Close"].iloc[0]) if count > 0 else 0

    return jsonify({
        "message": "Replay loaded",
        "symbol": symbol,
        "candles": count,
        "initial_cash": initial_cash,
    })


@simulation_bp.route("/simulation/replay/status", methods=["GET"])
def replay_status():
    status = _replay.get_status()
    candle = status.get("current_candle")
    prices = {}
    if candle:
        prices[status["symbol"]] = candle["close"]
    status["portfolio"] = _portfolio.to_dict(prices)
    return jsonify(status)


@simulation_bp.route("/simulation/replay/step", methods=["POST"])
def replay_step():
    candle = _replay.step()
    if not candle:
        return jsonify({"message": "End of data", "status": _replay.get_status()}), 200

    prices = {_replay.get_status()["symbol"]: candle.close}
    _record_portfolio_snapshot(prices)

    return jsonify({"candle": candle.to_dict(), "status": _replay.get_status()})


@simulation_bp.route("/simulation/replay/play", methods=["POST"])
def replay_play():
    _replay.play()
    return jsonify({"message": "Replay playing", "status": _replay.get_status()})


@simulation_bp.route("/simulation/replay/pause", methods=["POST"])
def replay_pause():
    _replay.pause()
    return jsonify({"message": "Replay paused", "status": _replay.get_status()})


@simulation_bp.route("/simulation/replay/speed", methods=["POST"])
def replay_speed():
    data = request.get_json(silent=True) or {}
    speed = int(data.get("speed", 1))
    actual = _replay.set_speed(speed)
    return jsonify({"speed": actual, "status": _replay.get_status()})


@simulation_bp.route("/simulation/replay/reset", methods=["POST"])
def replay_reset():
    _replay.reset()
    return jsonify({"message": "Replay reset", "status": _replay.get_status()})


# --- Manual Trading ---

@simulation_bp.route("/simulation/trade", methods=["POST"])
def manual_trade():
    """Execute manual BUY, SELL, or HOLD during replay."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").upper()
    symbol = data.get("symbol") or _replay.get_status().get("symbol", "AAPL")
    reason = data.get("reason", "")
    quantity = int(data.get("quantity", 0))

    candle = _replay.get_current_candle()
    if not candle and action != "HOLD":
        return jsonify({"error": "No active candle — load replay and step first"}), 400

    price = candle.close if candle else 0
    ts = candle.timestamp if candle else datetime.now().isoformat()

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
    status = _replay.get_status()
    symbol = status.get("symbol", "")
    prices = {}
    candle = status.get("current_candle")
    if candle and symbol:
        prices[symbol] = candle["close"]
    return jsonify(_portfolio.to_dict(prices))


# --- Performance Analytics ---

@simulation_bp.route("/performance", methods=["GET"])
def get_performance():
    """Comprehensive trading performance analytics."""
    status = _replay.get_status()
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
        benchmark_return = (candle["close"] - _benchmark_price) / _benchmark_price * 100

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
