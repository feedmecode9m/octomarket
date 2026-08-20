"""StrategyBacktestRunner — evaluate strategies through the full trader lifecycle."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..market.instrument import resolve_instrument
from ..replay.replay_session import get_replay_session
from ..strategies.registry import get_strategy_registry
from .benchmark import compute_benchmark_comparison
from .context import ResearchEnvironment, isolated_research_environment
from .costs import TransactionCostModel, summarize_transaction_costs
from .dates import apply_session_date_window
from .report import build_strategy_report
from .store import ResearchReportStore, get_research_report_store


class StrategyBacktestRunner:
    """
    Walk historical candles in REPLAY mode, generate TradePlans from strategies,
    execute through the standard pipeline, and aggregate DecisionScores.
    """

    def __init__(self, report_store: Optional[ResearchReportStore] = None):
        self._registry = get_strategy_registry()
        self._reports = report_store or get_research_report_store()

    def run(
        self,
        strategy_id: str,
        instrument_id: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
        initial_cash: float = 10000.0,
        cooldown_bars: int = 1,
        max_trades: Optional[int] = None,
        persist_report: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cost_model: Optional[TransactionCostModel] = None,
    ) -> Dict[str, Any]:
        strategy = self._registry.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy '{strategy_id}'")

        instrument = resolve_instrument(instrument_id)
        if instrument.asset_class.value not in strategy.asset_classes:
            raise ValueError(
                f"Strategy '{strategy_id}' does not support {instrument.asset_class.value}"
            )

        model = cost_model or TransactionCostModel.for_asset_class(instrument.asset_class.value)

        with isolated_research_environment(initial_cash=initial_cash, cost_model=model) as env:
            report = self._execute_run(
                env,
                strategy_id=strategy_id,
                strategy_name=strategy.name,
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol.upper(),
                asset_class=instrument.asset_class.value,
                continuous_id=instrument.continuous_id,
                period=period,
                interval=interval,
                min_bars=strategy.min_bars,
                cooldown_bars=cooldown_bars,
                max_trades=max_trades,
                start_date=start_date,
                end_date=end_date,
                cost_model=model,
                initial_cash=initial_cash,
            )

        if persist_report:
            self._reports.save(report)
        return report

    def _execute_run(
        self,
        env: ResearchEnvironment,
        *,
        strategy_id: str,
        strategy_name: str,
        instrument_id: str,
        symbol: str,
        asset_class: str,
        continuous_id: Optional[str],
        period: str,
        interval: str,
        min_bars: int,
        cooldown_bars: int,
        max_trades: Optional[int],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cost_model: Optional[TransactionCostModel] = None,
        initial_cash: float = 10000.0,
    ) -> Dict[str, Any]:
        replay = get_replay_session()
        replay.reset()
        replay.start(
            instrument_id=instrument_id,
            period=period,
            interval=interval,
            initial_cash=env.portfolio.initial_cash,
            reset_portfolio=False,
        )

        window_range = apply_session_date_window(
            replay._session,
            start_date=start_date,
            end_date=end_date,
        )
        if window_range.get("start"):
            date_range = window_range
        else:
            date_range = {"start": None, "end": None}

        closed_before = 0
        cooldown = 0
        trade_count = 0

        while True:
            state = replay.step()
            if state.get("error") or state.get("at_end"):
                break

            idx = state.get("current_index", -1)
            candles = state.get("candles") or {}
            candle = candles.get(symbol) or {}
            prices = state.get("prices") or {}
            price = prices.get(symbol) or candle.get("close") or 0

            if candle.get("timestamp"):
                ts = candle["timestamp"]
                date_range["start"] = date_range["start"] or ts
                date_range["end"] = ts

            equity = env.portfolio.get_portfolio_value({symbol: price} if price else {})
            env.equity_curve.append({"index": idx, "equity": round(equity, 2), "timestamp": candle.get("timestamp")})

            closed_now = len([r for r in env.store.list_all() if r.get("status") == "closed"])
            if closed_now > closed_before:
                closed_before = closed_now
                cooldown = cooldown_bars

            if cooldown > 0:
                cooldown -= 1
                continue

            if max_trades is not None and trade_count >= max_trades:
                continue

            if idx < min_bars:
                continue

            if self._has_open_exposure(env, symbol):
                continue

            result = env.engine.generate_plan(
                strategy_id,
                instrument_id,
                timeframe=interval,
                period=period,
                account_balance=equity,
                risk_percent=1.0,
            )
            plan = result.get("plan")
            if not plan:
                continue

            if self._submit_plan(env, plan, symbol):
                trade_count += 1

        self._finalize_open_position(env, symbol, replay.get_state())
        ohlcv = replay._session.get_ohlcv_frame(symbol)
        cost_summary = summarize_transaction_costs(
            cost_model=cost_model or TransactionCostModel.for_asset_class(asset_class),
            total_commission=env.portfolio.total_commissions,
            total_slippage=env.portfolio.total_slippage,
            trade_count=len([r for r in env.store.list_all() if r.get("status") == "closed"]),
        )
        benchmark = compute_benchmark_comparison(
            ohlcv=ohlcv,
            equity_curve=env.equity_curve,
            initial_cash=initial_cash,
            asset_class=asset_class,
        )
        replay.reset()

        records = env.store.list_all()
        return build_strategy_report(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            instrument_id=instrument_id,
            asset_class=asset_class,
            continuous_id=continuous_id,
            timeframe=interval,
            period=period,
            date_range=date_range,
            records=records,
            equity_curve=env.equity_curve,
            benchmark_comparison=benchmark,
            transaction_costs=cost_summary,
            initial_cash=initial_cash,
        )

    def _has_open_exposure(self, env: ResearchEnvironment, symbol: str) -> bool:
        key = symbol.upper()
        if key in env.portfolio.positions and env.portfolio.positions[key].quantity > 0:
            return True
        for order in env.orders.get_all("PENDING"):
            if order["symbol"] == key and order.get("role") == "entry":
                return True
        for record in env.store.list_all():
            if record.get("status") in ("filled", "submitted"):
                market = record.get("market") or {}
                if market.get("symbol", "").upper() == key or market.get("instrument_id", "").upper() == key:
                    return True
        return False

    def _submit_plan(self, env: ResearchEnvironment, plan: Dict[str, Any], symbol: str) -> bool:
        try:
            env.plans.review_plan(plan["id"])
            env.plans.approve_plan(plan["id"])
        except ValueError:
            return False

        payload = env.plans.build_order_payload(plan)
        try:
            order = env.orders.create_order(
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
        except ValueError:
            return False

        env.plans.mark_order_created(plan["id"], order["id"])
        env.memory.on_order_submitted(plan["id"], order["id"], order)
        return True

    def _finalize_open_position(
        self,
        env: ResearchEnvironment,
        symbol: str,
        state: Dict[str, Any],
    ) -> None:
        key = symbol.upper()
        prices = state.get("prices") or {}
        price = prices.get(key)
        if not price or key not in env.portfolio.positions:
            return
        qty = env.portfolio.positions[key].quantity
        if qty <= 0:
            return
        env.portfolio.sell(key, price, qty, reason="research finalize")
        env.memory.on_manual_close(key, price, quantity=qty)


_runner_instance: Optional[StrategyBacktestRunner] = None


def get_strategy_backtest_runner() -> StrategyBacktestRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = StrategyBacktestRunner()
    return _runner_instance
