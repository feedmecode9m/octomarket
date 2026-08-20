"""Learning journal API — evidence-backed trader improvement artifacts."""

from flask import Blueprint, jsonify, request

from ..learning.journal_service import get_learning_journal_service
from ..replay.replay_memory import get_replay_memory

journal_bp = Blueprint("learning_journal", __name__, url_prefix="/api/learning/journal")


@journal_bp.route("", methods=["GET"])
def list_journal_entries():
    instrument_id = request.args.get("instrument_id") or request.args.get("symbol")
    limit = request.args.get("limit", 50, type=int)
    journal = get_learning_journal_service()
    entries = journal.list_entries(limit=max(1, min(limit, 200)), instrument_id=instrument_id)
    return jsonify({"entries": entries, "count": len(entries)})


@journal_bp.route("/patterns", methods=["GET"])
def journal_patterns():
    min_trades = request.args.get("min_trades", 5, type=int)
    findings = get_learning_journal_service().recurring_patterns(
        min_trades=max(2, min(min_trades, 50))
    )
    return jsonify({"patterns": findings, "count": len(findings)})


@journal_bp.route("/record/<record_id>", methods=["GET"])
def journal_by_record(record_id):
    entry = get_learning_journal_service().get_by_record_id(record_id)
    if not entry:
        return jsonify({"error": "Learning journal entry not found"}), 404
    return jsonify({"entry": entry})


@journal_bp.route("/plan/<plan_id>", methods=["GET"])
def journal_by_plan(plan_id):
    entry = get_learning_journal_service().get_by_plan_id(plan_id)
    if not entry:
        return jsonify({"error": "Learning journal entry not found"}), 404
    return jsonify({"entry": entry})


@journal_bp.route("/generate/<plan_id>", methods=["POST"])
def journal_generate_for_plan(plan_id):
    """Backfill journal entry for an already-closed ReplayRecord."""
    record = get_replay_memory().get_by_plan_id(plan_id)
    if not record:
        return jsonify({"error": "Replay record not found"}), 404
    if record.get("status") != "closed":
        return jsonify({"error": "Trade must be closed before journaling"}), 400
    entry = get_learning_journal_service().on_record_closed(record)
    return jsonify({"entry": entry}), 201
