"""Market analysis for the AI Trading Coach."""

from typing import Any, Dict, List, Optional


class MarketAnalyzer:
    """Analyze market indicators and produce educational summaries."""

    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30

    def analyze(self, indicators: Dict[str, Any], prices: Optional[List[float]] = None) -> Dict[str, Any]:
        """Analyze indicators and return structured market assessment."""
        rsi = self._safe_float(indicators.get("rsi"))
        short_ma = self._safe_float(indicators.get("short_ma"))
        long_ma = self._safe_float(indicators.get("long_ma"))
        momentum = self._safe_float(indicators.get("price_momentum") or indicators.get("momentum"))
        volatility = self._safe_float(indicators.get("volatility"))
        volume_change = self._safe_float(indicators.get("volume_change_pct"))
        current_price = self._safe_float(indicators.get("current_price") or indicators.get("price"))

        ma_analysis = self._analyze_moving_averages(short_ma, long_ma, current_price)
        rsi_analysis = self._analyze_rsi(rsi)
        momentum_analysis = self._analyze_momentum(momentum)
        volatility_analysis = self._analyze_volatility(volatility, current_price)
        volume_analysis = self._analyze_volume(volume_change)

        trend = self._determine_trend(ma_analysis, momentum_analysis, rsi_analysis)

        return {
            "trend": trend,
            "moving_averages": ma_analysis,
            "rsi": rsi_analysis,
            "momentum": momentum_analysis,
            "volatility": volatility_analysis,
            "volume": volume_analysis,
            "support_resistance": self._estimate_support_resistance(prices or [], current_price),
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            result = float(value)
            if result != result:  # NaN check
                return None
            return result
        except (TypeError, ValueError):
            return None

    def _analyze_moving_averages(
        self, short_ma: Optional[float], long_ma: Optional[float], price: Optional[float]
    ) -> Dict[str, Any]:
        if short_ma is None or long_ma is None:
            return {
                "signal": "insufficient_data",
                "explanation": "Not enough data to calculate moving averages yet. Wait for more price history.",
            }

        if short_ma > long_ma:
            signal = "bullish"
            explanation = (
                f"The short-term MA (${short_ma:.2f}) is above the long-term MA (${long_ma:.2f}), "
                "indicating upward momentum. This is called a 'golden cross' setup when it first occurs."
            )
        elif short_ma < long_ma:
            signal = "bearish"
            explanation = (
                f"The short-term MA (${short_ma:.2f}) is below the long-term MA (${long_ma:.2f}), "
                "suggesting downward pressure. A 'death cross' occurs when the short MA crosses below the long MA."
            )
        else:
            signal = "neutral"
            explanation = "Moving averages are converging — the trend direction is unclear."

        price_vs_ma = None
        if price is not None:
            if price > short_ma:
                price_vs_ma = "Price is trading above the short MA — bulls are in control near-term."
            elif price < short_ma:
                price_vs_ma = "Price is below the short MA — short-term sellers dominate."

        return {"signal": signal, "short_ma": short_ma, "long_ma": long_ma, "explanation": explanation, "price_context": price_vs_ma}

    def _analyze_rsi(self, rsi: Optional[float]) -> Dict[str, Any]:
        if rsi is None:
            return {"value": None, "zone": "unknown", "explanation": "RSI data not available."}

        if rsi >= self.RSI_OVERBOUGHT:
            zone = "overbought"
            explanation = (
                f"RSI is {rsi:.1f} — in overbought territory (>{self.RSI_OVERBOUGHT}). "
                "The asset may be overextended; consider waiting for a pullback before buying."
            )
        elif rsi <= self.RSI_OVERSOLD:
            zone = "oversold"
            explanation = (
                f"RSI is {rsi:.1f} — in oversold territory (<{self.RSI_OVERSOLD}). "
                "This can signal a potential bounce, but confirm with other indicators."
            )
        else:
            zone = "neutral"
            explanation = f"RSI is {rsi:.1f} — in neutral range. No extreme overbought or oversold signal."

        return {"value": rsi, "zone": zone, "explanation": explanation}

    def _analyze_momentum(self, momentum: Optional[float]) -> Dict[str, Any]:
        if momentum is None:
            return {"direction": "unknown", "explanation": "Momentum data not available."}

        if momentum > 0.01:
            direction = "strong_up"
            explanation = f"Momentum is strongly positive ({momentum:.2%}). Price is accelerating upward."
        elif momentum > 0:
            direction = "up"
            explanation = f"Momentum is slightly positive ({momentum:.2%}). Gentle upward drift."
        elif momentum < -0.01:
            direction = "strong_down"
            explanation = f"Momentum is strongly negative ({momentum:.2%}). Price is falling quickly."
        elif momentum < 0:
            direction = "down"
            explanation = f"Momentum is slightly negative ({momentum:.2%}). Gentle downward drift."
        else:
            direction = "flat"
            explanation = "Momentum is flat — price is consolidating."

        return {"value": momentum, "direction": direction, "explanation": explanation}

    def _analyze_volatility(self, volatility: Optional[float], price: Optional[float]) -> Dict[str, Any]:
        if volatility is None or price is None or price <= 0:
            return {"level": "unknown", "explanation": "Volatility data not available."}

        vol_pct = (volatility / price) * 100
        if vol_pct > 3:
            level = "high"
            explanation = (
                f"Volatility is high ({vol_pct:.1f}% of price). "
                "Expect larger price swings — use wider stop losses and smaller position sizes."
            )
        elif vol_pct > 1.5:
            level = "moderate"
            explanation = f"Moderate volatility ({vol_pct:.1f}%). Normal trading conditions."
        else:
            level = "low"
            explanation = f"Low volatility ({vol_pct:.1f}%). Price is relatively stable."

        return {"level": level, "volatility_pct": round(vol_pct, 2), "explanation": explanation}

    def _analyze_volume(self, volume_change: Optional[float]) -> Dict[str, Any]:
        if volume_change is None:
            return {"trend": "unknown", "explanation": "Volume change data not available."}

        if volume_change > 20:
            trend = "surging"
            explanation = f"Volume is up {volume_change:.0f}% — strong participation confirms the move."
        elif volume_change > 5:
            trend = "increasing"
            explanation = f"Volume is increasing ({volume_change:.0f}%). Growing interest in this symbol."
        elif volume_change < -20:
            trend = "declining"
            explanation = f"Volume is down {abs(volume_change):.0f}% — the move may lack conviction."
        else:
            trend = "stable"
            explanation = "Volume is relatively stable."

        return {"trend": trend, "change_pct": volume_change, "explanation": explanation}

    def _determine_trend(
        self,
        ma: Dict[str, Any],
        momentum: Dict[str, Any],
        rsi: Dict[str, Any],
    ) -> str:
        bullish_signals = 0
        bearish_signals = 0

        if ma.get("signal") == "bullish":
            bullish_signals += 1
        elif ma.get("signal") == "bearish":
            bearish_signals += 1

        if momentum.get("direction") in ("up", "strong_up"):
            bullish_signals += 1
        elif momentum.get("direction") in ("down", "strong_down"):
            bearish_signals += 1

        if rsi.get("zone") == "oversold":
            bullish_signals += 1
        elif rsi.get("zone") == "overbought":
            bearish_signals += 1

        if bullish_signals > bearish_signals:
            return "bullish"
        if bearish_signals > bullish_signals:
            return "bearish"
        return "neutral"

    def _estimate_support_resistance(
        self, prices: List[float], current_price: Optional[float]
    ) -> Dict[str, Any]:
        if not prices or current_price is None:
            return {"support": None, "resistance": None, "explanation": "Insufficient price history."}

        recent = prices[-20:] if len(prices) >= 20 else prices
        support = min(recent)
        resistance = max(recent)

        return {
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "explanation": (
                f"Recent support near ${support:.2f}, resistance near ${resistance:.2f}. "
                "Support is where buyers tend to step in; resistance is where sellers appear."
            ),
        }
