"""Isolated research environment — same pipeline, separate state."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from ..replay.replay_memory import ReplayMemory
from ..replay.replay_store import ReplayStore
from ..simulation.paper_portfolio import PaperPortfolio
from ..simulation.session import MarketSession
from ..strategies.engine import StrategyEngine
from ..trading.execution import ExecutionSimulator
from ..trading.order_engine import OrderEngine
from ..trading.trade_plan import TradePlanManager


@dataclass
class ResearchEnvironment:
    """Bundled isolated components for a strategy research run."""

    store: ReplayStore
    memory: ReplayMemory
    plans: TradePlanManager
    orders: OrderEngine
    portfolio: PaperPortfolio
    executor: ExecutionSimulator
    engine: StrategyEngine
    session: MarketSession
    equity_curve: list = field(default_factory=list)
    _temp_dir: Optional[tempfile.TemporaryDirectory] = None


@contextmanager
def isolated_research_environment(
    *,
    store_path: Optional[Path] = None,
    initial_cash: float = 10000.0,
) -> Iterator[ResearchEnvironment]:
    """Patch global trading/replay services to isolated instances for one research run."""
    temp = None
    if store_path is None:
        temp = tempfile.TemporaryDirectory()
        store_path = Path(temp.name) / "records.jsonl"

    store = ReplayStore(path=store_path)
    memory = ReplayMemory(store=store)
    plans = TradePlanManager(record_replay=True, replay_memory=memory)
    orders = OrderEngine()
    portfolio = PaperPortfolio(initial_cash=initial_cash)
    portfolio.reset(initial_cash)
    executor = ExecutionSimulator(order_engine=orders, portfolio=portfolio)
    engine = StrategyEngine(plan_manager=plans)
    session = MarketSession()

    env = ResearchEnvironment(
        store=store,
        memory=memory,
        plans=plans,
        orders=orders,
        portfolio=portfolio,
        executor=executor,
        engine=engine,
        session=session,
        _temp_dir=temp,
    )

    import src.api.execution_routes as execution_routes
    import src.replay.replay_memory as replay_memory_mod
    import src.replay.replay_session as replay_session_mod
    import src.replay.replay_store as replay_store_mod
    import src.simulation.paper_portfolio as paper_portfolio_mod
    import src.simulation.session as session_mod
    import src.trading.execution as execution_mod
    import src.trading.order_engine as order_engine_mod
    import src.trading.trade_plan as trade_plan_mod

    originals = {
        "replay_memory": replay_memory_mod._memory_instance,
        "replay_store": replay_store_mod._store_instance,
        "trade_plan": trade_plan_mod._manager_instance,
        "orders": order_engine_mod._engine_instance,
        "executor": execution_mod._simulator_instance,
        "portfolio": paper_portfolio_mod._portfolio_instance,
        "session": session_mod._session_instance,
        "process_fills": execution_routes.process_session_fills,
    }

    def _patched_fills(candles: dict) -> list:
        from .fills import process_research_fills

        return process_research_fills(
            candles,
            orders=env.orders,
            executor=env.executor,
            memory=env.memory,
        )

    replay_memory_mod._memory_instance = memory
    replay_store_mod._store_instance = store
    trade_plan_mod._manager_instance = plans
    order_engine_mod._engine_instance = orders
    execution_mod._simulator_instance = executor
    paper_portfolio_mod._portfolio_instance = portfolio
    session_mod._session_instance = session
    execution_routes.process_session_fills = _patched_fills

    try:
        yield env
    finally:
        replay_memory_mod._memory_instance = originals["replay_memory"]
        replay_store_mod._store_instance = originals["replay_store"]
        trade_plan_mod._manager_instance = originals["trade_plan"]
        order_engine_mod._engine_instance = originals["orders"]
        execution_mod._simulator_instance = originals["executor"]
        paper_portfolio_mod._portfolio_instance = originals["portfolio"]
        session_mod._session_instance = originals["session"]
        execution_routes.process_session_fills = originals["process_fills"]
        if temp is not None:
            temp.cleanup()
