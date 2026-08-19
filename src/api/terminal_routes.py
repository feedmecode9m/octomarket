"""Terminal, watchlist, session, alerts, and commentary API routes."""

import pandas as pd
from flask import Blueprint, jsonify, request

from ..ai_agent.market_commentator import get_market_commentator
from ..core.data_fetcher import DataFetcher
from ..market.alerts import get_alert_manager
from ..market.watchlist import get_watchlist
from ..simulation.events import get_event_engine
from ..simulation.paper_portfolio import get_paper_portfolio
from ..simulation.session import get_market_session

terminal_bp = Blueprint("terminal", __name__, url_prefix="/api")

_watchlist = get_watchlist()
_session = get_market_session()
_portfolio = get_paper_portfolio()
_alerts = get_alert_manager()
_events = get_event_engine()
_commentator = get_market_commentator()


def _compute_rsi(prices: pd.Series, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
    return round(100 - (100 / (1 + rs)), 2)


def _fetch_price(symbol: str) -> tuple:
    fetcher = DataFetcher(symbol=symbol, interval="1d", period="5d")
    df = fetcher.get_real_time_data()
    if df.empty:
        return 0.0, 0.0
    price = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2]) if len(df) > 1 else price
    return price, prev


def _sync_watchlist_prices():
    for entry in _watchlist.get_all():
        sym = entry["symbol"]
        if entry.get("price", 0) <= 0:
            price, prev = _fetch_price(sym)
            if price > 0:
                _watchlist.update_price(sym, price, prev)


# --- Watchlist ---

@terminal_bp.route("/watchlist", methods=["GET"])
def get_watchlist_route():
    _sync_watchlist_prices()
    return jsonify(_watchlist.get_all())


@terminal_bp.route("/watchlist", methods=["POST"])
def add_to_watchlist():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").upper()
    if not symbol:
        return jsonify({"error": "Symbol required"}), 400

    try:
        price, prev = _fetch_price(symbol)
        entry = _watchlist.add(symbol, price, prev)
        return jsonify({"message": f"{symbol} added", "entry": entry})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@terminal_bp.route("/watchlist/<symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    removed = _watchlist.remove(symbol)
    if not removed:
        return jsonify({"error": f"{symbol} not in watchlist"}), 404
    return jsonify({"message": f"{symbol} removed"})


# --- Market Session ---

@terminal_bp.route("/session/start", methods=["POST"])
def start_session():
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols") or _watchlist.get_symbols()
    if not symbols:
        symbols = ["AAPL"]

    initial_cash = float(data.get("initial_cash", 10000))
    period = data.get("period", "5d")
    interval = data.get("interval", "1d")

    try:
        _portfolio.reset(initial_cash)
        _events.clear()
        state = _session.start(symbols, initial_cash, period, interval)
        return jsonify({"message": "Session started", "state": state})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@terminal_bp.route("/session/step", methods=["POST"])
def step_session():
    state = _session.step()
    if "error" in state:
        return jsonify(state), 400

    triggered = []
    for symbol, price in state.get("prices", {}).items():
        prev = state.get("prev_closes", {}).get(symbol, price)
        _watchlist.update_price(symbol, price, prev)
        triggered.extend(_alerts.check_price_alerts(symbol, price, prev))

        chart = _session.get_chart_data(symbol)
        if chart.get("prices"):
            rsi = _compute_rsi(pd.Series(chart["prices"]))
            triggered.extend(_alerts.check_indicator_alerts(symbol, rsi))

        event = _events.maybe_generate(symbol, state.get("current_index", 0))
        if event:
            state.setdefault("events", []).append(event)

    portfolio = _portfolio.to_dict(state.get("prices", {}))
    risk_event = _alerts.check_portfolio_risk(portfolio.get("risk_score", 0))
    if risk_event:
        triggered.append(risk_event)

    state["alerts_triggered"] = triggered
    state["portfolio"] = portfolio
    return jsonify(state)


@terminal_bp.route("/session/pause", methods=["POST"])
def pause_session():
    _session.pause()
    return jsonify(_session.get_state())


@terminal_bp.route("/session/resume", methods=["POST"])
def resume_session():
    _session.resume()
    return jsonify(_session.get_state())


@terminal_bp.route("/session/close", methods=["POST"])
def close_session():
    _session.close()
    return jsonify({"message": "Session closed", "state": _session.get_state()})


@terminal_bp.route("/session/state", methods=["GET"])
def session_state():
    state = _session.get_state()
    state["portfolio"] = _portfolio.to_dict(state.get("prices", {}))
    return jsonify(state)


@terminal_bp.route("/session/chart/<symbol>", methods=["GET"])
def session_chart(symbol):
    return jsonify(_session.get_chart_data(symbol))


# --- Alerts ---

@terminal_bp.route("/alerts", methods=["GET"])
def list_alerts():
    return jsonify({
        "alerts": _alerts.get_all(),
        "triggered": _alerts.get_triggered(),
    })


@terminal_bp.route("/alerts", methods=["POST"])
def create_alert():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "")
    alert_type = data.get("type", "price")
    condition = data.get("condition", "drops")
    threshold = float(data.get("threshold", 5))
    message = data.get("message", "")

    if not symbol and alert_type != "portfolio_risk":
        return jsonify({"error": "Symbol required"}), 400

    alert = _alerts.create(symbol or "PORTFOLIO", alert_type, condition, threshold, message)
    return jsonify({"message": "Alert created", "alert": alert})


@terminal_bp.route("/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    if not _alerts.delete(alert_id):
        return jsonify({"error": "Alert not found"}), 404
    return jsonify({"message": "Alert deleted"})


# --- Commentary & Events ---

@terminal_bp.route("/commentary", methods=["GET"])
def get_commentary():
    session_state = _session.get_state()
    watchlist = _watchlist.get_all()
    portfolio = _portfolio.to_dict(session_state.get("prices", {}))
    triggered = _alerts.get_triggered()

    commentary = _commentator.commentate(portfolio, watchlist, session_state, triggered)
    return jsonify(commentary)


@terminal_bp.route("/events", methods=["GET"])
def get_events():
    return jsonify({"events": _events.get_recent()})


# --- Terminal Trading ---

@terminal_bp.route("/terminal/trade", methods=["POST"])
def terminal_trade():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").lower()
    symbol = data.get("symbol", "").upper()
    quantity = int(data.get("quantity", 0))
    reason = data.get("reason", "")

    session_state = _session.get_state()
    prices = session_state.get("prices", {})

    if action == "hold":
        result = _portfolio.hold(symbol, reason)
        return jsonify(result)

    if not symbol:
        return jsonify({"error": "Symbol required"}), 400

    price = prices.get(symbol)
    if not price or price <= 0:
        price, _ = _fetch_price(symbol)

    if action == "buy":
        if quantity <= 0:
            return jsonify({"error": "Quantity required for buy"}), 400
        result = _portfolio.buy(symbol, price, quantity, reason=reason)
    elif action == "sell":
        result = _portfolio.sell(symbol, price, quantity if quantity > 0 else None, reason=reason)
    else:
        return jsonify({"error": "Action must be buy, sell, or hold"}), 400

    result["portfolio"] = _portfolio.to_dict(prices)
    return jsonify(result)


@terminal_bp.route("/terminal/portfolio", methods=["GET"])
def terminal_portfolio():
    session_state = _session.get_state()
    prices = session_state.get("prices", {})
    if not prices:
        for entry in _watchlist.get_all():
            if entry.get("price", 0) > 0:
                prices[entry["symbol"]] = entry["price"]
    return jsonify(_portfolio.to_dict(prices))
