"""Order execution API routes — TradingView-style paper trading."""

from typing import Optional

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


def _current_prices(for_symbol: Optional[str] = None) -> dict:
    """Mode-aware prices: REPLAY uses session closes; LIVE never does."""
    from ..market.live_price import resolve_execution_prices

    return resolve_execution_prices(for_symbol=for_symbol)


def _record_fill_in_journal(order: dict, fill: dict):
    """Record fills for ReplayRecord lifecycle — not the legacy AI trade journal."""
    role = order.get("role", "entry")
    if role == "entry" and order["side"] == "buy":
        _record_replay_fill(order, fill, exit_reason=None)
        _cancel_duplicate_plan_entries(order)
    elif role in ("stop_loss", "take_profit") and order["side"] == "sell":
        _record_replay_fill(order, fill, exit_reason=role)


def _cancel_duplicate_plan_entries(filled_order: dict) -> None:
    """If a plan-linked entry fills (e.g. market ticket), cancel leftover plan limit entries."""
    plan_id = (filled_order.get("trade_plan") or {}).get("plan_id")
    if not plan_id:
        return
    for other in _orders.get_pending():
        if other["id"] == filled_order["id"]:
            continue
        if other.get("role", "entry") != "entry":
            continue
        if (other.get("trade_plan") or {}).get("plan_id") != plan_id:
            continue
        _orders.cancel_order(other["id"])


def _record_replay_fill(order: dict, fill: dict, exit_reason: Optional[str]):
    from ..replay.replay_memory import get_replay_memory

    memory = get_replay_memory()
    if exit_reason:
        memory.on_exit_fill(order, fill, exit_reason=exit_reason)
    else:
        memory.on_entry_fill(order, fill)


@execution_bp.route("/orders", methods=["POST"])
def place_order():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").upper()
    side = data.get("side", "buy").lower()
    quantity = int(data.get("quantity", 0))
    order_type = data.get("order_type", "market").lower()

    if not symbol or quantity <= 0:
        return jsonify({"error": "Symbol and quantity required"}), 400

    plan_context = data.get("trade_plan") or {}
    try:
        order = _orders.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=data.get("limit_price") or data.get("price"),
            stop_price=data.get("stop_price"),
            stop_loss=data.get("stop_loss") or plan_context.get("stop_loss"),
            take_profit=data.get("take_profit"),
            bracket=data.get("bracket", False),
            trade_plan={
                "plan_id": plan_context.get("plan_id"),
                "why_enter": plan_context.get("why_enter") or data.get("why_enter", ""),
                "setup": plan_context.get("setup") or data.get("setup", ""),
                "expected_move": plan_context.get("expected_move") or data.get("expected_move", ""),
                "invalidation": plan_context.get("invalidation") or data.get("invalidation", ""),
                "stop_loss": plan_context.get("stop_loss") or data.get("stop_loss"),
                "thesis": plan_context.get("thesis"),
            },
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    prices = _current_prices(for_symbol=symbol)
    price = float(prices.get(symbol) or 0)

    if order_type == "market":
        from ..replay.replay_session import is_replay_mode

        if price <= 0:
            # Never fall back to residual replay closes for LIVE fills.
            _orders.mark_rejected(
                order["id"],
                "No valid LIVE price available for market execution",
            )
            order = _orders.get_order(order["id"])
            msg = (
                "No valid replay session price available for market execution"
                if is_replay_mode()
                else (
                    "No valid LIVE price available for market execution. "
                    "Add the symbol to the watchlist or ensure a live quote can be fetched."
                )
            )
            return jsonify({"error": msg, "order": order}), 400

        fill_result = _executor.process_market_order(order, price)
        order = _orders.get_order(order["id"])
        if fill_result.get("status") == "FILLED":
            _record_fill_in_journal(order, fill_result.get("fill", {}))
        elif fill_result.get("status") == "REJECTED":
            return jsonify({"error": fill_result.get("error", "Order rejected"), "order": order}), 400

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

    prices = _current_prices(for_symbol=symbol)
    price = float(prices.get(symbol) or 0)
    if price <= 0:
        from ..replay.replay_session import is_replay_mode

        msg = (
            "No valid replay session price available"
            if is_replay_mode()
            else "No valid LIVE price available"
        )
        return jsonify({"error": msg}), 400

    pos = _portfolio.to_dict(prices).get("positions", {}).get(symbol)
    if not pos:
        return jsonify({"error": f"No position in {symbol}"}), 400

    result = _portfolio.sell(symbol, price, pos["quantity"], reason="close position")
    if not result.get("success"):
        return jsonify({"error": result.get("error")}), 400

    for order in _orders.get_pending():
        if order["symbol"] == symbol:
            _orders.cancel_order(order["id"])

    pos_qty = pos.get("quantity")
    from ..replay.replay_memory import get_replay_memory

    get_replay_memory().on_manual_close(symbol, price, quantity=pos_qty)

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
    """User-facing trade history — canonical Learning Journal entries."""
    from ..learning.journal_service import get_learning_journal_service
    from ..replay.replay_memory import get_replay_memory

    entries = get_learning_journal_service().list_entries(limit=50)
    memory = get_replay_memory()
    history = []
    for entry in entries:
        outcome = entry.get("outcome_snapshot") or entry.get("outcome") or {}
        scoring = entry.get("scoring_snapshot") or entry.get("scoring") or {}
        plan_id = entry.get("plan_id")
        record = memory.get_by_plan_id(plan_id) if plan_id else None
        execution = (record or {}).get("execution") or {}
        entry_fill = execution.get("entry") or {}
        exit_fill = execution.get("exit") or {}
        history.append({
            "id": entry.get("id"),
            "plan_id": plan_id,
            "symbol": entry.get("instrument_id") or entry.get("symbol"),
            "date": entry.get("date"),
            "entry_price": entry_fill.get("price"),
            "exit_price": exit_fill.get("price"),
            "duration": None,
            "result": {
                "pnl": outcome.get("pnl"),
                "win_loss": outcome.get("win_loss"),
                "r_multiple": outcome.get("r_multiple"),
            },
            "decision_score": scoring.get("decision_score"),
            "decision_summary": entry.get("decision_summary"),
            "trade_plan": {
                "setup": entry.get("strategy_name") or entry.get("strategy_id") or "manual",
            },
        })
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
    return jsonify({"history": history, "fills": fills[-50:], "source": "learning_journal"})


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
