"""Transaction cost model for research runs — spread, commission, slippage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TransactionCostModel:
    """Configurable execution assumptions applied during research replay."""

    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    spread_bps: float = 0.0
    per_contract_commission: float = 0.0
    execution_delay_bars: int = 0
    label: str = "default"

    def effective_slippage_rate(self) -> float:
        """Half-spread applied per fill plus explicit slippage."""
        spread_rate = self.spread_bps / 10_000.0
        return self.slippage_rate + (spread_rate / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["effective_slippage_rate"] = round(self.effective_slippage_rate(), 6)
        return payload

    @classmethod
    def for_asset_class(cls, asset_class: str) -> "TransactionCostModel":
        asset = (asset_class or "").upper()
        if asset == "FOREX":
            return cls(
                commission_rate=0.0,
                slippage_rate=0.00005,
                spread_bps=15.0,
                execution_delay_bars=0,
                label="forex_retail",
            )
        if asset == "FUTURES":
            return cls(
                commission_rate=0.00015,
                slippage_rate=0.0002,
                spread_bps=2.0,
                per_contract_commission=2.25,
                execution_delay_bars=0,
                label="futures_retail",
            )
        return cls(label="equity_default")


def summarize_transaction_costs(
    *,
    cost_model: TransactionCostModel,
    total_commission: float,
    total_slippage: float,
    trade_count: int,
) -> Dict[str, Any]:
    """Summarize costs applied during a research run."""
    total_costs = round(total_commission + total_slippage, 2)
    spread_estimate = round(total_slippage, 2)
    return {
        "cost_model": cost_model.to_dict(),
        "total_commission": round(total_commission, 2),
        "total_slippage": round(total_slippage, 2),
        "total_costs": total_costs,
        "cost_per_trade": round(total_costs / trade_count, 2) if trade_count else None,
        "spread_included_in_slippage": spread_estimate,
        "execution_delay_bars": cost_model.execution_delay_bars,
    }


def gross_profit_metrics(
    closed_records: list,
    total_costs: float,
) -> Dict[str, Optional[float]]:
    """Estimate pre-cost profitability by restoring round-trip costs to net PnL."""
    pnls = [
        (r.get("outcome") or {}).get("pnl")
        for r in closed_records
        if (r.get("outcome") or {}).get("pnl") is not None
    ]
    if not pnls:
        return {
            "profit_factor_gross": None,
            "total_pnl_gross": None,
            "cost_impact_pct": None,
        }

    cost_per_trade = total_costs / len(pnls) if pnls else 0.0
    gross_pnls = [p + cost_per_trade for p in pnls]
    wins = [p for p in gross_pnls if p > 0]
    losses = [abs(p) for p in gross_pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    net_total = sum(pnls)

    pf_gross = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    impact = None
    if net_total != 0:
        impact = round((sum(gross_pnls) - net_total) / abs(net_total) * 100, 1)

    return {
        "profit_factor_gross": pf_gross,
        "total_pnl_gross": round(sum(gross_pnls), 2),
        "cost_impact_pct": impact,
    }
