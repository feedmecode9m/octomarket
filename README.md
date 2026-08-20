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

Copy `env.example` to `.env` for local overrides. Do not commit secrets.

## Local vs production

| | Local | Production |
|---|---|---|
| Start | `python app.py` | `gunicorn app:app` (Docker uses `docker-entrypoint.sh`) |
| Debug | `FLASK_DEBUG` defaults **on** unless `ENV=production` | `ENV=production` and `FLASK_DEBUG=False` |
| Data | `./data` | `DATA_DIR=/data` (Railway volume mount) |
| Health | `GET /health` | `GET /health` |

Health response (cheap liveness only — no store scans):

```json
{"status": "ok", "service": "OctoMarket", "version": "17B"}
```

### Persistent volume

JSONL stores stay file-backed. Mount a volume at **`/data`** and set `DATA_DIR=/data`.

```text
/data
 ├── replay/      records.jsonl, patterns.jsonl
 ├── learning/    journal.jsonl
 └── research/    reports.jsonl
```

TradePlan / OrderEngine remain in-process memory. Production uses **one Gunicorn worker** so those objects are not split across processes.

### Required environment variables (production)

| Variable | Purpose |
|---|---|
| `ENV` | Set to `production` (disables debug unless `FLASK_DEBUG` is set) |
| `FLASK_DEBUG` | Must be `False` in production |
| `SECRET_KEY` | Flask secret — do not use the repo default |
| `DATA_DIR` | Persistence root; `/data` when a volume is mounted |
| `PORT` | Bind port (Railway injects this) |
| `DEPLOYMENT_GATE` | Optional `/health` version label (default `17B`) |

## Testing

```bash
pytest
```

## Paper Trading Only

OctoMarket is educational software. It does not connect to brokers, execute real money trades, or provide autonomous trading.

## License

MIT
