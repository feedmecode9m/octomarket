"""Strategy engine — evaluate signals and create TradePlans through existing pipeline."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..market.instrument import resolve_instrument
from ..trading.trade_plan import TradePlanManager, get_trade_plan_manager
from .context import StrategyContext, build_strategy_context
from .registry import StrategyRegistry, get_strategy_registry
from .risk import StrategyRiskModel
from .signal import StrategySignal


class StrategyEngine:
    """Orchestrate strategy evaluation → TradePlan creation."""

    def __init__(
        self,
        registry: Optional[StrategyRegistry] = None,
        plan_manager: Optional[TradePlanManager] = None,
        risk_model: Optional[StrategyRiskModel] = None,
    ):
        self._registry = registry or get_strategy_registry()
        self._plans = plan_manager or get_trade_plan_manager()
        self._risk = risk_model or StrategyRiskModel()

    def evaluate(
        self,
        strategy_id: str,
        instrument_id: str,
        *,
        timeframe: Optional[str] = None,
        period: Optional[str] = None,
        account_balance: Optional[float] = None,
        risk_percent: Optional[float] = None,
    ) -> Dict[str, Any]:
        strategy = self._registry.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy '{strategy_id}'")

        instrument = resolve_instrument(instrument_id)
        if instrument.asset_class.value not in strategy.asset_classes:
            raise ValueError(
                f"Strategy '{strategy_id}' does not support {instrument.asset_class.value}"
            )

        tf = timeframe or strategy.default_timeframe
        lookback = period or strategy.default_period
        context = build_strategy_context(instrument.instrument_id, timeframe=tf, period=lookback)

        if context.bar_count < strategy.min_bars:
            return {
                "signal": None,
                "reason": f"Insufficient bars ({context.bar_count}/{strategy.min_bars})",
                "context": self._context_summary(context),
            }

        raw_signal = strategy.evaluate(context)
        if raw_signal is None:
            return {
                "signal": None,
                "reason": "No setup — strategy conditions not met",
                "context": self._context_summary(context),
            }

        signal = self._risk.apply(
            raw_signal,
            context,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )
        return {
            "signal": signal.to_dict(),
            "reason": None,
            "context": self._context_summary(context),
        }

    def generate_plan(
        self,
        strategy_id: str,
        instrument_id: str,
        *,
        timeframe: Optional[str] = None,
        period: Optional[str] = None,
        account_balance: Optional[float] = None,
        risk_percent: Optional[float] = None,
    ) -> Dict[str, Any]:
        result = self.evaluate(
            strategy_id,
            instrument_id,
            timeframe=timeframe,
            period=period,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )
        if not result.get("signal"):
            return {**result, "plan": None}

        signal = self._signal_from_dict(result["signal"])
        plan_data = self._plan_payload(signal)
        plan = self._plans.create_plan(plan_data)
        return {**result, "plan": plan}

    def _plan_payload(self, signal: StrategySignal) -> Dict[str, Any]:
        sizing = signal.metadata.get("sizing") or {}
        kwargs: Dict[str, Any] = {
            "account_balance": signal.metadata.get("account_balance"),
            "risk_percent": signal.metadata.get("risk_percent"),
        }
        if signal.asset_class == AssetClass.FOREX.value:
            kwargs["position_lots"] = sizing.get("lots", 0.1)
        elif signal.asset_class == AssetClass.FUTURES.value:
            kwargs["contracts"] = sizing.get("contracts", 1)
        else:
            kwargs["quantity"] = sizing.get("quantity", 10)
        return signal.to_plan_data(**kwargs)

    def _signal_from_dict(self, data: Dict[str, Any]) -> StrategySignal:
        return StrategySignal(
            strategy_id=data["strategy_id"],
            strategy_name=data["strategy_name"],
            instrument_id=data["instrument_id"],
            asset_class=data["asset_class"],
            direction=data["direction"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            target=data["target"],
            confidence=data["confidence"],
            setup_reasons=list(data.get("setup") or []),
            risk_reasons=list(data.get("risk") or []),
            indicators=dict(data.get("indicators") or {}),
            metadata=dict(data.get("metadata") or {}),
        )

    def _context_summary(self, context: StrategyContext) -> Dict[str, Any]:
        return {
            "instrument_id": context.instrument_id,
            "asset_class": context.asset_class,
            "bar_count": context.bar_count,
            "current_price": context.current_price,
            "session_capped": context.session_capped,
            "cap_index": context.cap_index,
            "continuous_id": context.continuous_id,
        }


_engine_instance: Optional[StrategyEngine] = None


def get_strategy_engine() -> StrategyEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = StrategyEngine()
    return _engine_instance
