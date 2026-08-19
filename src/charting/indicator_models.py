"""Indicator specification and result models for the chart analysis layer."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class IndicatorSpec:
    """Parsed indicator request (e.g. SMA20, EMA9, MACD)."""

    key: str
    indicator_type: str
    period: Optional[int] = None
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def pane(self) -> str:
        if self.indicator_type in ("RSI", "MACD"):
            return "sub"
        return "overlay"


@dataclass
class SeriesResult:
    """Single-value indicator output aligned to candle timestamps."""

    indicator: str
    period: Optional[int] = None
    values: List[Optional[float]] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"indicator": self.indicator, "values": self.values}
        if self.period is not None:
            payload["period"] = self.period
        if self.params:
            payload.update(self.params)
        return payload


@dataclass
class MacdResult:
    """MACD line, signal, and histogram."""

    indicator: str = "MACD"
    fast: int = 12
    slow: int = 26
    signal: int = 9
    macd: List[Optional[float]] = field(default_factory=list)
    signal_line: List[Optional[float]] = field(default_factory=list)
    histogram: List[Optional[float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator": self.indicator,
            "fast": self.fast,
            "slow": self.slow,
            "signal_period": self.signal,
            "macd": self.macd,
            "signal": self.signal_line,
            "histogram": self.histogram,
        }


@dataclass
class BollingerResult:
    """Bollinger upper, middle, lower bands."""

    indicator: str = "BB"
    period: int = 20
    stddev: float = 2.0
    upper: List[Optional[float]] = field(default_factory=list)
    middle: List[Optional[float]] = field(default_factory=list)
    lower: List[Optional[float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator": self.indicator,
            "period": self.period,
            "stddev": self.stddev,
            "upper": self.upper,
            "middle": self.middle,
            "lower": self.lower,
        }
