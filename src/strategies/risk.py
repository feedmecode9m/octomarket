"""Strategy risk model — ATR stops and account-aware sizing."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..market.asset_class import AssetClass
from ..simulation.paper_portfolio import get_paper_portfolio
from .context import StrategyContext
from .signal import StrategySignal
from .technical import compute_atr, last_valid


class StrategyRiskModel:
    """Apply consistent risk rules to strategy signals before plan creation."""

    DEFAULT_RISK_PERCENT = 1.0
    DEFAULT_ATR_STOP_MULT = 2.0
    DEFAULT_ATR_TARGET_MULT = 4.0
    MIN_RR = 2.0

    def apply(
        self,
        signal: StrategySignal,
        context: StrategyContext,
        *,
        account_balance: Optional[float] = None,
        risk_percent: Optional[float] = None,
        atr_stop_mult: Optional[float] = None,
        atr_target_mult: Optional[float] = None,
    ) -> StrategySignal:
        """Refine stop/target and attach sizing hints using ATR when needed."""
        balance = account_balance if account_balance is not None else self._account_balance()
        risk_pct = risk_percent if risk_percent is not None else self.DEFAULT_RISK_PERCENT
        stop_mult = atr_stop_mult or self.DEFAULT_ATR_STOP_MULT
        target_mult = atr_target_mult or self.DEFAULT_ATR_TARGET_MULT

        atr = last_valid(compute_atr(context.highs, context.lows, context.closes, 14))
        entry = signal.entry_price
        direction = signal.direction.upper()

        if atr and atr > 0:
            if direction == "LONG":
                stop = entry - atr * stop_mult
                target = entry + atr * target_mult
            else:
                stop = entry + atr * stop_mult
                target = entry - atr * target_mult

            stop, target = self._sanitize_levels(
                signal.asset_class, direction, entry, stop, target, atr
            )

            if self._valid_levels(direction, entry, stop, target):
                signal.stop_loss = round(stop, 6)
                signal.target = round(target, 6)
                signal.risk_reasons.append(f"ATR({atr:.4f}) stop at {stop_mult}x, target at {target_mult}x")
                signal.indicators["ATR14"] = round(atr, 6)

        self._ensure_min_rr(signal)
        signal.metadata["account_balance"] = balance
        signal.metadata["risk_percent"] = risk_pct
        signal.metadata["sizing"] = self._sizing_hint(signal, balance, risk_pct)
        return signal

    def _ensure_min_rr(self, signal: StrategySignal) -> None:
        entry = signal.entry_price
        stop = signal.stop_loss
        target = signal.target
        direction = signal.direction.upper()
        if direction == "LONG":
            risk = entry - stop
            reward = target - entry
        else:
            risk = stop - entry
            reward = entry - target
        if risk <= 0 or reward <= 0:
            return
        rr = reward / risk
        if rr >= self.MIN_RR:
            signal.risk_reasons.append(f"Risk/reward {rr:.1f}:1 meets guideline")
            return
        if direction == "LONG":
            signal.target = round(entry + risk * self.MIN_RR, 6)
        else:
            signal.target = round(entry - risk * self.MIN_RR, 6)
        signal.risk_reasons.append(f"Target adjusted to {self.MIN_RR}:1 minimum R:R")

    def _sizing_hint(
        self,
        signal: StrategySignal,
        balance: float,
        risk_percent: float,
    ) -> Dict[str, Any]:
        if signal.asset_class == AssetClass.FOREX.value:
            from ..trading.position_sizing import calculate_forex_size

            try:
                return calculate_forex_size(
                    balance,
                    risk_percent,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.instrument_id,
                )
            except ValueError:
                return {"position_lots": 0.1}
        if signal.asset_class == AssetClass.FUTURES.value:
            from ..market.futures import calculate_futures_size

            try:
                return calculate_futures_size(
                    balance,
                    risk_percent,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.instrument_id,
                )
            except ValueError:
                return {"contracts": 1}
        risk_amount = round(balance * (risk_percent / 100), 2)
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        qty = max(1, int(risk_amount / risk_per_share)) if risk_per_share > 0 else 10
        return {"quantity": qty, "risk_amount": risk_amount}

    def _sanitize_levels(
        self,
        asset_class: str,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        atr: float,
    ) -> tuple:
        """Ensure stops/targets stay valid for asset price scale."""
        if asset_class == AssetClass.FOREX.value:
            max_stop_dist = max(atr * 2, entry * 0.01)
            min_stop_dist = entry * 0.001
        elif asset_class == AssetClass.FUTURES.value:
            max_stop_dist = max(atr * 3, entry * 0.01)
            min_stop_dist = max(atr * 0.5, entry * 0.001)
        else:
            max_stop_dist = max(atr * 3, entry * 0.02)
            min_stop_dist = max(atr * 0.5, entry * 0.005)

        if direction == "LONG":
            stop_dist = entry - stop
            if stop_dist <= 0 or stop_dist > max_stop_dist:
                stop = entry - min(max_stop_dist, max(min_stop_dist, atr * 2))
            if target <= entry:
                target = entry + min(max_stop_dist * 2, atr * 4)
        else:
            stop_dist = stop - entry
            if stop_dist <= 0 or stop_dist > max_stop_dist:
                stop = entry + min(max_stop_dist, max(min_stop_dist, atr * 2))
            if target >= entry:
                target = entry - min(max_stop_dist * 2, atr * 4)
        return stop, target

    def _valid_levels(self, direction: str, entry: float, stop: float, target: float) -> bool:
        if direction == "LONG":
            return stop < entry < target
        return target < entry < stop

    def _account_balance(self) -> float:
        portfolio = get_paper_portfolio()
        return float(portfolio.get_portfolio_value({}) or portfolio.cash or portfolio.initial_cash)
