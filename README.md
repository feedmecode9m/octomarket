# OctoMarket

**Practice. Analyze. Execute. Improve.**

OctoMarket is an AI-powered trading practice terminal. Learn order execution, strategy building, and risk management with paper money only — no broker connections, no real trades.

![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Version](https://img.shields.io/badge/Version-0.1.0-teal)

## Product Modules

| Module | Path | Description |
|--------|------|-------------|
| **Terminal** | `/terminal` | TradingView-style order execution |
| **Mentor** | `/mentor` | AI trading coach |
| **Lab** | `/strategy-lab` | Strategy testing & backtesting |
| **Replay** | `/replay` | Market simulation |
| **Academy** | `/academy` | Lessons and challenges |
| **Journal** | `/journal` | Trade reviews |

## Features

- **Candlestick Terminal** — TradingView-style chart workspace with volume, crosshair, and timeframes
- **Order Execution** — Market, limit, stop, bracket orders with fill simulation
- **AI Mentor** — Personalized coaching, mistake detection, adaptive lessons
- **Strategy Lab** — Natural-language strategy parsing and backtesting
- **Paper Portfolio** — Multi-position tracking with risk scoring
- **Market Replay** — Candle-by-candle simulation
- **Trade Journal** — Trade plans and execution reviews

## Quick Start

```bash
git clone https://github.com/feedmecode9m/octomarket.git
cd octomarket
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** for the OctoMarket home dashboard.

## Configuration

Product identity is centralized in `src/config/product.py`:

```python
PRODUCT_NAME = "OctoMarket"
VERSION = "0.1.0"
TAGLINE = "Practice. Analyze. Execute. Improve."
```

## Testing

```bash
pytest
```

## Paper Trading Only

OctoMarket is educational software. It does not connect to brokers, execute real money trades, or provide autonomous trading.

## License

MIT
