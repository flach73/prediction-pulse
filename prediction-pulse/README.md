# Prediction Pulse 📊

A mini prediction markets dashboard that pulls live odds from Kalshi, stores them in a database, and displays a simple dashboard with current prices and historical charts.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Live Data Ingestion**: Fetches market data from Kalshi's public API
- **Local Storage**: SQLite database for simplicity and portability
- **Interactive Dashboard**: Streamlit-based UI with filters and charts
- **Price History**: Track probability changes over time

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/prediction-pulse.git
cd prediction-pulse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python init_db.py
```

### 3. Fetch Market Data

```bash
# Fetch all open markets
python ingest_kalshi.py

# Or filter by category
python ingest_kalshi.py --category politics

# See all options
python ingest_kalshi.py --help
```

### 4. Launch Dashboard

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Project Structure

```
prediction-pulse/
├── app.py                    # Streamlit dashboard
├── db.py                     # SQLAlchemy models
├── init_db.py                # Database initialization
├── fetch_kalshi_markets.py   # Kalshi API client
├── ingest_kalshi.py          # ETL script
├── requirements.txt          # Python dependencies
├── prediction_pulse.db       # SQLite database (created on first run)
└── README.md
```

## Data Model

Three tables capture market structure and price history:

**markets** - Metadata per prediction market
- `market_id`: Kalshi's unique identifier
- `title`: Human-readable question
- `category`: Market category (politics, economics, etc.)
- `status`: open, closed, settled
- `expiry_ts`: Resolution date

**contracts** - Tradeable options within a market
- `contract_ticker`: Kalshi's contract symbol
- `side`: YES or NO
- `market_id`: Foreign key to markets

**prices** - Time-series price snapshots
- `contract_id`: Foreign key to contracts
- `timestamp`: When the price was recorded
- `bid_price`, `ask_price`, `last_price`: Prices in cents (= probability %)
- `volume_24h`: 24-hour trading volume

## Building Price History

To build meaningful price charts, run the ingestion script periodically:

```bash
# Manual: run every few minutes
python ingest_kalshi.py

# Automated (Linux/Mac): add to crontab
# Run every 10 minutes
*/10 * * * * cd /path/to/prediction-pulse && python ingest_kalshi.py --quiet
```

## Deployment to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo and select `app.py`
4. Deploy!

**Note**: SQLite on Streamlit Cloud is ephemeral (resets on redeploys). For persistent data:
- Pre-populate the database and commit `prediction_pulse.db`
- Or use a cloud database (Turso, Supabase, etc.)

## API Reference

### Kalshi API

This project uses Kalshi's public API endpoints:

- `GET /trade-api/v2/markets` - List markets
- `GET /trade-api/v2/markets/{ticker}` - Market details

No authentication required for read-only access to public markets.

### Rate Limits

Kalshi's public API has rate limits. The ingestion script is designed to stay well within these limits, but avoid running it more frequently than every 5 minutes.

## Future Enhancements (v2+)

- [ ] Add Polymarket data source
- [ ] Whale tracking (large trades)
- [ ] Email/webhook alerts for price movements
- [ ] React/Next.js frontend
- [ ] Historical data backfill

## License

MIT
