"""Strategy Lab API endpoints."""

from flask import Blueprint, jsonify, request

from ..ai_agent.agent import TradingCoachAgent
from ..core.data_fetcher import DataFetcher
from ..learning.skill_score import SkillScoreCalculator
from ..models.state import get_simulator_state
from ..strategy_lab.backtester import StrategyBacktester
from ..strategy_lab.comparator import StrategyComparator
from ..strategy_lab.library import get_strategy_by_id, get_strategy_library
from ..strategy_lab.strategy_builder import StrategyBuilder

strategy_lab_bp = Blueprint("strategy_lab", __name__, url_prefix="/api/strategy")

_builder = StrategyBuilder()
_backtester = StrategyBacktester()
_comparator = StrategyComparator(_backtester)
_coach = TradingCoachAgent()
_simulator_state = get_simulator_state()

_last_backtest: dict = {}


@strategy_lab_bp.route("/parse", methods=["POST"])
def parse_strategy():
    """Convert natural-language description to rules."""
    try:
        data = request.get_json(silent=True) or {}
        description = data.get("description", "")
        name = data.get("name", "Custom Strategy")

        if data.get("rules"):
            result = _builder.parse_rules(data["rules"], name)
        else:
            result = _builder.parse(description, name)

        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@strategy_lab_bp.route("/backtest", methods=["POST"])
def backtest_strategy():
    """Run strategy backtest on historical data."""
    global _last_backtest
    try:
        data = request.get_json(silent=True) or {}
        strategy = data.get("strategy")
        if not strategy:
            description = data.get("description")
            if description:
                strategy = _builder.parse(description, data.get("name", "Custom"))
            else:
                return jsonify({"error": "strategy or description required"}), 400

        symbol = data.get("symbol", "AAPL")
        period = data.get("period", "1mo")
        interval = data.get("interval", "1d")
        initial_cash = float(data.get("initial_cash", 10000))

        fetcher = DataFetcher(symbol=symbol, interval=interval, period=period)
        ohlcv = fetcher.get_real_time_data()
        if ohlcv.empty:
            return jsonify({"error": "No data available"}), 404

        result = _backtester.run(strategy, ohlcv, symbol, initial_cash)
        _last_backtest = result
        from ..api.simulation_routes import set_last_backtest_result
        set_last_backtest_result(result)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Backtest failed: {str(e)}"}), 500


@strategy_lab_bp.route("/compare", methods=["POST"])
def compare_strategies():
    """Compare multiple strategies vs buy-and-hold."""
    try:
        data = request.get_json(silent=True) or {}
        strategies = data.get("strategies", [])
        if not strategies:
            return jsonify({"error": "At least one strategy required"}), 400

        symbol = data.get("symbol", "AAPL")
        period = data.get("period", "1mo")
        interval = data.get("interval", "1d")
        initial_cash = float(data.get("initial_cash", 10000))

        fetcher = DataFetcher(symbol=symbol, interval=interval, period=period)
        ohlcv = fetcher.get_real_time_data()
        if ohlcv.empty:
            return jsonify({"error": "No data available"}), 404

        result = _comparator.compare(strategies, ohlcv, symbol, initial_cash)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@strategy_lab_bp.route("/library", methods=["GET"])
def list_library():
    return jsonify({"strategies": get_strategy_library()})


@strategy_lab_bp.route("/library/<strategy_id>", methods=["GET"])
def get_library_strategy(strategy_id):
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return jsonify({"error": "Strategy not found"}), 404
    return jsonify(strategy)


# Skill score also available at GET /api/skill-score via simulation_bp
