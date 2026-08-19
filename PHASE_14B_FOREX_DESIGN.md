# Phase 14B — Forex Trading Layer

## Objective

Correct forex mechanics before UI or replay. OctoMarket must size positions from account risk, not share counts.

## Modules

```
src/market/forex.py           pip_size, pip_value, lot_to_units, pip_distance
src/trading/position_sizing.py calculate_forex_size
src/trading/risk.py           max_loss, reward_ratio, account_risk_percent
src/models/position.py        asset-aware position model
```

## Lot sizing formula

```
Risk Amount = Account × Risk %
Pip Risk    = |Entry − Stop| / Pip Size
Lot Size    = Risk Amount / (Pip Risk × Pip Value per lot)
```

Example (EURUSD, $50k account, 1% risk, 50 pip stop):

```
Risk = $500
Pip value = $10 / standard lot
Lots = 500 / (50 × 10) = 1.00
```

## Trade plan fields (FOREX)

| Field | Example |
|-------|---------|
| asset_class | FOREX |
| instrument_id | EURUSD |
| position_lots | 1.00 |
| pip_risk | 50 |
| reward_pips | 100 |
| risk_amount | 500 USD |
| risk_reward | 2.0 |

## Chart model

Chart workspace uses `instrument_id` + `asset_class` (symbol retained for compatibility).

## Gate

450+ pytest passing before Phase 14C futures engine.
