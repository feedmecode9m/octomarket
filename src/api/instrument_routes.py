"""Instrument catalog and resolution API."""

from flask import Blueprint, jsonify, request

from ..market.asset_class import AssetClass
from ..market.instrument import list_instruments, resolve_instrument
from ..market.session_rules import get_session_rules

instrument_bp = Blueprint("instruments", __name__, url_prefix="/api/instruments")


@instrument_bp.route("", methods=["GET"])
def get_instruments():
    """List supported instruments, optionally filtered by asset_class."""
    asset_class = request.args.get("asset_class")
    if asset_class:
        try:
            ac = AssetClass.from_value(asset_class)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        items = list_instruments(ac)
    else:
        items = list_instruments()
    return jsonify({"instruments": items, "count": len(items)})


@instrument_bp.route("/<path:instrument_id>", methods=["GET"])
def get_instrument(instrument_id):
    """Resolve a single instrument with session metadata."""
    try:
        instrument = resolve_instrument(instrument_id)
        payload = instrument.to_dict()
        session = get_session_rules(instrument.asset_class, instrument.exchange)
        payload["session"] = session.to_dict()
        return jsonify(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
