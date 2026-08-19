"""Order execution API routes — TradingView-style paper trading."""

from flask import Blueprint, jsonify, request

from ..ai_agent.execution_coach import get_execution_coach
from ..ai_agent.trade_journal import get_trade_journal
from ..simulation.paper_portfolio import get_paper_portfolio
from ..simulation.session import get_market_session
from ..trading.execution import get_execution_simulator
from ..trading.order_engine import get_order_engine

execution_bp = Blueprint("execution", __name__, url_prefix="/api")

_orders = get_order_engine()
_executor = get_execution_simulator()
_portfolio = get_paper_portfolio()
_session = get_market_session()
_journal = get_trade_journal()
_coach = get_execution_coach()

_peak_equity = 10000.0


def _current_prices() -> dict:
    state = _session.get_state()
    prices = dict(state.get("prices", {}))
    if not prices:
        from ..market.watchlist import get_watchlist
        for entry in get_watchlist().get_all():
            if entry.get("price", 0) > 0:
                prices[entry["symbol"]] = entry["price"]
    return prices


def _record_fill_in_journal(order: dict, fill: dict):
    role = order.get("role", "entry")
    if role == "entry" and order["side"] == "buy":
        _journal.record_execution(
            symbol=order["symbol"],
            side=order["side"],
            entry_price=fill.get("fill_price", 0),
            quantity=fill.get("quantity", order["quantity"]),
            order_id=order["id"],
            trade_plan=order.get("trade_plan"),
        )
    elif role in ("stop_loss", "take_profit") and order["side"] == "sell":
        parent_id = order.get("parent_id")
        if parent_id:
            _journal.close_by_order_id(parent_id, fill.get("fill_price", 0))


@execution_bp.route("/orders", methods=["POST"])
def place_order():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").upper()
    side = data.get("side", "buy").lower()
    quantity = int(data.get("quantity", 0))
    order_type = data.get("order_type", "market").lower()

    if not symbol or quantity <= 0:
        return jsonify({"error": "Symbol and quantity required"}), 400

    try:
        order = _orders.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=data.get("limit_price") or data.get("price"),
            stop_price=data.get("stop_price"),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            bracket=data.get("bracket", False),
            trade_plan={
                "why_enter": data.get("why_enter", ""),
                "setup": data.get("setup", ""),
                "expected_move": data.get("expected_move", ""),
                "invalidation": data.get("invalidation", ""),
                "stop_loss": data.get("stop_loss"),
            },
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    prices = _current_prices()
    price = prices.get(symbol, data.get("limit_price") or data.get("price") or 0)

    if order_type == "market" and price > 0:
        fill_result = _executor.process_market_order(order, price)
        order = _orders.get_order(order["id"])
        if fill_result.get("status") == "FILLED":
            _record_fill_in_journal(order, fill_result.get("fill", {}))

    return jsonify({"message": "Order placed", "order": order})


@execution_bp.route("/orders", methods=["GET"])
def list_orders():
    status = request.args.get("status")
    return jsonify({"orders": _orders.get_all(status)})


@execution_bp.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    order = _orders.get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)


@execution_bp.route("/orders/<order_id>", methods=["PUT"])
def update_order(order_id):
    data = request.get_json(silent=True) or {}
    order = _orders.update_order(order_id, **data)
    if not order:
        return jsonify({"error": "Order not found or not editable"}), 404
    return jsonify({"message": "Order updated", "order": order})


@execution_bp.route("/orders/<order_id>", methods=["DELETE"])
def cancel_order(order_id):
    order = _orders.cancel_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({"message": "Order cancelled", "order": order})


@execution_bp.route("/orders/close-position", methods=["POST"])
def close_position():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").upper()
    if not symbol:
        return jsonify({"error": "Symbol required"}), 400

    prices = _current_prices()
    price = prices.get(symbol, 0)
    if price <= 0:
        return jsonify({"error": "No price available"}), 400

    pos = _portfolio.to_dict(prices).get("positions", {}).get(symbol)
    if not pos:
        return jsonify({"error": f"No position in {symbol}"}), 400

    result = _portfolio.sell(symbol, price, pos["quantity"], reason="close position")
    if not result.get("success"):
        return jsonify({"error": result.get("error")}), 400

    for order in _orders.get_pending():
        if order["symbol"] == symbol:
            _orders.cancel_order(order["id"])

    for entry in _journal.get_all():
        if entry["symbol"] == symbol and entry["status"] == "open":
            _journal.update_exit(entry["id"], price)
            break

    return jsonify({"message": "Position closed", "result": result})


@execution_bp.route("/terminal/account", methods=["GET"])
def terminal_account():
    global _peak_equity
    prices = _current_prices()
    portfolio = _portfolio.to_dict(prices)
    equity = portfolio.get("total_value", 0)
    _peak_equity = max(_peak_equity, equity)
    drawdown = (_peak_equity - equity) / _peak_equity * 100 if _peak_equity > 0 else 0

    return jsonify({
        "balance": portfolio.get("cash", 0),
        "equity": equity,
        "initial_balance": portfolio.get("initial_cash", 0),
        "margin_used": 0,
        "margin_available": portfolio.get("cash", 0),
        "unrealized_pnl": portfolio.get("unrealized_pnl", 0),
        "realized_pnl": portfolio.get("realized_pnl", 0),
        "drawdown_pct": round(drawdown, 2),
        "peak_equity": round(_peak_equity, 2),
        "total_return_pct": portfolio.get("total_return_pct", 0),
    })


@execution_bp.route("/terminal/history", methods=["GET"])
def terminal_history():
    history = _journal.get_history()
    fills = []
    for record in _portfolio.trade_history:
        fills.append({
            "timestamp": record.timestamp,
            "symbol": record.symbol,
            "action": record.action,
            "quantity": record.quantity,
            "fill_price": record.fill_price,
            "commission": record.commission,
        })
    return jsonify({"history": history, "fills": fills[-50:]})


@execution_bp.route("/journal/<entry_id>/review", methods=["PUT"])
def journal_review(entry_id):
    data = request.get_json(silent=True) or {}
    entry = _journal.add_execution_review(
        entry_id,
        review={
            "entry_good": data.get("entry_good"),
            "risk_controlled": data.get("risk_controlled"),
            "exit_disciplined": data.get("exit_disciplined"),
            "notes": data.get("notes", ""),
        },
        exit_price=data.get("exit_price"),
    )
    if not entry:
        return jsonify({"error": "Journal entry not found"}), 404
    return jsonify({"message": "Review saved", "entry": entry})


def process_session_fills(candles: dict) -> list:
    """Called from session step to process pending orders."""
    fills = _executor.process_all_symbols(candles)
    for fill in fills:
        if fill.get("status") in ("FILLED", "PARTIAL_FILL"):
            order = _orders.get_order(fill["order_id"])
            if order:
                _record_fill_in_journal(order, fill.get("fill", {}))
    return fills
