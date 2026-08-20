"""Trade plan API — thesis and risk layer before order execution."""

from flask import Blueprint, jsonify, request

from ..simulation.paper_portfolio import get_paper_portfolio
from ..trading.execution import get_execution_simulator
from ..trading.order_engine import get_order_engine
from ..trading.trade_plan import get_trade_plan_manager

trade_plan_bp = Blueprint("trade_plan", __name__, url_prefix="/api/trade-plan")

_plans = get_trade_plan_manager()
_orders = get_order_engine()
_executor = get_execution_simulator()
_portfolio = get_paper_portfolio()


def _current_prices(for_symbol=None) -> dict:
    from ..market.live_price import resolve_execution_prices

    return resolve_execution_prices(for_symbol=for_symbol)


@trade_plan_bp.route("", methods=["POST"])
def create_trade_plan():
    data = request.get_json(silent=True) or {}
    try:
        plan = _plans.create_plan(data)
        return jsonify({"message": "Trade plan created", "plan": plan}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trade_plan_bp.route("/<symbol>", methods=["GET"])
def get_trade_plans_for_symbol(symbol):
    symbol = symbol.upper()
    items = _plans.get_plans_for_symbol(symbol)
    active = items[0] if items else None
    return jsonify({"symbol": symbol, "plans": items, "active": active})


@trade_plan_bp.route("/id/<plan_id>", methods=["GET"])
def get_trade_plan(plan_id):
    plan = _plans.get_plan(plan_id)
    if not plan:
        return jsonify({"error": f"Trade plan '{plan_id}' not found"}), 404
    return jsonify(plan)


@trade_plan_bp.route("/<plan_id>", methods=["PUT"])
def update_trade_plan(plan_id):
    data = request.get_json(silent=True) or {}
    try:
        plan = _plans.update_plan(plan_id, data)
        return jsonify({"message": "Trade plan updated", "plan": plan})
    except KeyError:
        return jsonify({"error": f"Trade plan '{plan_id}' not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trade_plan_bp.route("/<plan_id>/review", methods=["POST"])
def review_trade_plan(plan_id):
    data = request.get_json(silent=True) or {}
    notes = data.get("notes") or []
    if data.get("setup"):
        _plans.update_plan(plan_id, {"setup": data["setup"]})
    try:
        plan = _plans.review_plan(plan_id, notes=notes)
        return jsonify({"message": "Trade plan reviewed", "plan": plan})
    except KeyError:
        return jsonify({"error": f"Trade plan '{plan_id}' not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trade_plan_bp.route("/<plan_id>/approve", methods=["POST"])
def approve_trade_plan(plan_id):
    try:
        plan = _plans.approve_plan(plan_id)
        return jsonify({"message": "Trade plan approved", "plan": plan})
    except KeyError:
        return jsonify({"error": f"Trade plan '{plan_id}' not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trade_plan_bp.route("/<plan_id>/create-order", methods=["POST"])
def create_order_from_plan(plan_id):
    plan = _plans.get_plan(plan_id)
    if not plan:
        return jsonify({"error": f"Trade plan '{plan_id}' not found"}), 404

    if plan["status"] == "DRAFT":
        try:
            plan = _plans.review_plan(plan_id)
            plan = _plans.approve_plan(plan_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    elif plan["status"] == "REVIEWED":
        try:
            plan = _plans.approve_plan(plan_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    elif plan["status"] != "APPROVED":
        return jsonify({"error": f"Plan status '{plan['status']}' cannot create order"}), 400

    payload = _plans.build_order_payload(plan)
    try:
        order = _orders.create_order(
            symbol=payload["symbol"],
            side=payload["side"],
            quantity=payload["quantity"],
            order_type=payload["order_type"],
            limit_price=payload["limit_price"],
            stop_loss=payload["stop_loss"],
            take_profit=payload["take_profit"],
            bracket=payload["bracket"],
            trade_plan=payload["trade_plan"],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    prices = _current_prices()
    price = prices.get(plan["symbol"], plan["entry"]["price"])
    if payload["order_type"] == "market" and price > 0:
        _executor.process_market_order(order, price)
        order = _orders.get_order(order["id"])

    updated = _plans.mark_order_created(plan_id, order["id"])
    return jsonify({
        "message": "Order created from trade plan",
        "plan": updated,
        "order": order,
    }), 201
