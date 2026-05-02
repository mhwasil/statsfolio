# Statsfolio

A modern web dashboard for visualizing and analyzing your Ghostfolio portfolio data, built with Dash, AG Grid, and Plotly.

## Features

- **Dashboard** — Portfolio KPIs (net worth, invested, performance, annualized return, XIRR, TWRR), portfolio evolution chart, allocation pie chart, performance bar chart, and top holdings table.
- **Analysis** — Performance breakdown, computed return metrics (MWRR, TWRR), full holdings table, monthly returns, drawdown, cash flow, and recent activities.
- **Activities** — Transaction history with buy/sell/dividend badges, per-activity currency, and pagination.
- **Theme Toggle** — Switch between dark and light themes, persisted across sessions.

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your Ghostfolio host and access token

docker build -t statsfolio .
docker run -p 3000:3000 --env-file .env statsfolio
```

Open `http://localhost:3000` in your browser.

## Local Development

1. Copy the example environment file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your Ghostfolio host and access token.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   PYTHONPATH=.:$PYTHONPATH uvicorn app.main:server --host 0.0.0.0 --port 3000
   ```

4. Open `http://localhost:3000` in your browser.

## Requirements

- Python 3.10+
- Ghostfolio instance (self-hosted or ghostfol.io)
- Dependencies listed in `requirements.txt`

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GHOSTFOLIO_HOST` | Yes | – | Ghostfolio instance URL (no trailing slash) |
| `GHOSTFOLIO_TOKEN` | Yes | – | Your access token from Ghostfolio settings |

## Project Structure

```
├── app/
│   ├── main.py          # Dash app (routes, callbacks, layouts)
│   ├── api_client.py    # Ghostfolio API wrapper
│   ├── analyzer.py      # Portfolio analysis (XIRR, TWRR, allocations)
│   ├── config.py        # Settings and environment variables
│   ├── models.py        # Pydantic data models
│   └── assets/
│       └── style.css    # Dashboard styles and theme variables
├── statsfolio/
│   ├── __init__.py      # Package entry (re-exports Client, GhostfolioError)
│   ├── exceptions.py    # Custom exception classes
│   └── statsfolio_client.py  # Ghostfolio REST API client
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```
