"""Convert natural-language strategy descriptions into executable rules."""

import re
from typing import Any, Dict, List, Optional


class StrategyBuilder:
    """Rule-based parser for simple strategy descriptions. No LLM required."""

    MA_CROSSOVER_PATTERNS = [
        re.compile(
            r"(?:buy|enter\s+long)\s+when\s+(?:the\s+)?(\d+)\s*(?:day|period)?\s*"
            r"(?:day\s+)?(?:moving average|ma|sma|ema)\s+crosses?\s+above\s+(?:the\s+)?(\d+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(\d+)\s*(?:day|period)?\s*(?:day\s+)?(?:moving average|ma|sma|ema)\s+cross(?:es)?\s+above\s+(\d+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:sell|exit|close)\s+when\s+(?:the\s+)?(\d+)\s*(?:day|period)?\s*"
            r"(?:day\s+)?(?:moving average|ma|sma|ema)\s+crosses?\s+below\s+(?:the\s+)?(\d+)",
            re.IGNORECASE,
        ),
    ]

    RSI_PATTERNS = [
        re.compile(
            r"(?:buy|enter)\s+when\s+rsi\s+(?:goes?\s+)?below\s+(\d+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:sell|exit)\s+when\s+rsi\s+(?:goes?\s+)?above\s+(\d+)",
            re.IGNORECASE,
        ),
        re.compile(r"rsi\s+(?:is\s+)?(?:above|over)\s+(\d+)", re.IGNORECASE),
        re.compile(r"rsi\s+(?:is\s+)?(?:below|under)\s+(\d+)", re.IGNORECASE),
    ]

    MACD_PATTERNS = [
        re.compile(
            r"(?:buy|enter)\s+when\s+macd\s+cross(?:es)?\s+above\s+(?:signal|zero)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:sell|exit)\s+when\s+macd\s+cross(?:es)?\s+below\s+(?:signal|zero)",
            re.IGNORECASE,
        ),
    ]

    SUPPORT_PATTERNS = [
        re.compile(
            r"(?:buy|enter)\s+(?:at|on|when\s+(?:price\s+)?(?:hits?|reaches?|bounces?\s+(?:off|at)))\s+support",
            re.IGNORECASE,
        ),
    ]

    VOLATILITY_PATTERNS = [
        re.compile(
            r"(?:buy|enter)\s+on\s+volatility\s+breakout",
            re.IGNORECASE,
        ),
    ]

    def parse(self, description: str, name: str = "Custom Strategy") -> Dict[str, Any]:
        """Parse a strategy description into a structured rule set."""
        if not description or not description.strip():
            raise ValueError("Strategy description cannot be empty")

        rules: List[Dict[str, Any]] = []
        text = description.strip()

        rules.extend(self._parse_ma_crossover(text))
        rules.extend(self._parse_rsi(text))
        rules.extend(self._parse_macd(text))
        rules.extend(self._parse_support(text))
        rules.extend(self._parse_volatility(text))

        if not rules:
            rules = self._parse_fallback(text)

        return {
            "name": name,
            "description": description,
            "rules": rules,
            "risk_per_trade": 0.02,
            "stop_loss": 0.01,
            "take_profit": 0.02,
        }

    def parse_rules(self, rules: List[Dict[str, Any]], name: str = "Custom Strategy") -> Dict[str, Any]:
        """Validate and wrap pre-built rules."""
        if not rules:
            raise ValueError("At least one rule is required")
        for rule in rules:
            self._validate_rule(rule)
        return {
            "name": name,
            "description": "User-defined rules",
            "rules": rules,
            "risk_per_trade": 0.02,
            "stop_loss": 0.01,
            "take_profit": 0.02,
        }

    def _parse_ma_crossover(self, text: str) -> List[Dict[str, Any]]:
        rules = []
        for pattern in self.MA_CROSSOVER_PATTERNS:
            for match in pattern.finditer(text):
                fast = int(match.group(1))
                slow = int(match.group(2))
                action = "SELL" if "below" in match.group(0).lower() else "BUY"
                indicator = "EMA" if "ema" in match.group(0).lower() else "SMA"
                rules.append({
                    "indicator": indicator,
                    "fast_period": fast,
                    "slow_period": slow,
                    "signal": "crossover",
                    "direction": "below" if action == "SELL" else "above",
                    "action": action,
                })
        return rules

    def _parse_rsi(self, text: str) -> List[Dict[str, Any]]:
        rules = []
        for pattern in self.RSI_PATTERNS:
            for match in pattern.finditer(text):
                threshold = int(match.group(1))
                snippet = match.group(0).lower()
                if "sell" in snippet or "exit" in snippet or "above" in snippet or "over" in snippet:
                    action = "SELL"
                    condition = "above"
                else:
                    action = "BUY"
                    condition = "below"
                rules.append({
                    "indicator": "RSI",
                    "period": 14,
                    "threshold": threshold,
                    "condition": condition,
                    "action": action,
                })
        return rules

    def _parse_macd(self, text: str) -> List[Dict[str, Any]]:
        rules = []
        for pattern in self.MACD_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0).lower()
                action = "SELL" if "sell" in snippet or "exit" in snippet or "below" in snippet else "BUY"
                rules.append({
                    "indicator": "MACD",
                    "signal": "crossover",
                    "direction": "below" if action == "SELL" else "above",
                    "action": action,
                })
        return rules

    def _parse_support(self, text: str) -> List[Dict[str, Any]]:
        rules = []
        for pattern in self.SUPPORT_PATTERNS:
            if pattern.search(text):
                rules.append({
                    "indicator": "SUPPORT",
                    "lookback": 20,
                    "signal": "bounce",
                    "action": "BUY",
                })
        return rules

    def _parse_volatility(self, text: str) -> List[Dict[str, Any]]:
        rules = []
        for pattern in self.VOLATILITY_PATTERNS:
            if pattern.search(text):
                rules.append({
                    "indicator": "VOLATILITY",
                    "period": 20,
                    "multiplier": 1.5,
                    "signal": "breakout",
                    "action": "BUY",
                })
        return rules

    def _parse_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Best-effort fallback when no pattern matches."""
        lower = text.lower()
        if "rsi" in lower:
            if "sell" in lower or "above" in lower:
                return [{"indicator": "RSI", "period": 14, "threshold": 70, "condition": "above", "action": "SELL"}]
            return [{"indicator": "RSI", "period": 14, "threshold": 30, "condition": "below", "action": "BUY"}]
        if "moving average" in lower or " ma " in f" {lower} ":
            return [{
                "indicator": "SMA",
                "fast_period": 20,
                "slow_period": 50,
                "signal": "crossover",
                "direction": "above",
                "action": "BUY",
            }]
        raise ValueError(
            "Could not parse strategy. Try: 'Buy when 20 day MA crosses above 50 day MA' "
            "or 'Sell when RSI goes above 70'."
        )

    def _validate_rule(self, rule: Dict[str, Any]):
        if "indicator" not in rule:
            raise ValueError("Each rule must have an indicator")
        if "action" not in rule:
            raise ValueError("Each rule must have an action (BUY or SELL)")
