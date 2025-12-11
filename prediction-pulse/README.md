# Prediction Pulse 📊

A mini prediction markets dashboard that pulls live odds from **Kalshi** and **Polymarket**, stores them in a database, and displays a simple dashboard with current prices and historical charts.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Multi-Source Data**: Fetches from both Kalshi and Polymarket APIs
- **Source Filtering**: Filter markets by data source
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
# Fetch from ALL sources (recommended)
python ingest_all.py

# Or fetch from individual sources
python ingest_kalshi.py --limit 50
python ingest_polymarket.py --limit 50

# See all options
python ingest_all.py --help
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
├── db.py                     # SQLAlchemy models (with source column)
├── init_db.py                # Database initialization
├── fetch_kalshi_markets.py   # Kalshi API client
├── fetch_polymarket.py       # Polymarket API client
├── ingest_kalshi.py          # Kalshi ETL script
├── ingest_polymarket.py      # Polymarket ETL script
├── ingest_all.py             # Combined ETL for all sources
├── seed_sample_data.py       # Sample data generator
├── requirements.txt          # Python dependencies
├── prediction_pulse.db       # SQLite database (created on first run)
└── README.md
```

## Data Model

Three tables capture market structure and price history:

**markets** - Metadata per prediction market
- `market_id`: Source's unique identifier
- `source`: Data source ("kalshi" or "polymarket")
- `title`: Human-readable question
- `category`: Market category (politics, crypto, etc.)
- `status`: open, closed, settled
- `expiry_ts`: Resolution date

**contracts** - Tradeable options within a market
- `contract_ticker`: Source's contract symbol
- `side`: YES or NO
- `market_id`: Foreign key to markets

**prices** - Time-series price snapshots
- `contract_id`: Foreign key to contracts
- `timestamp`: When the price was recorded
- `bid_price`, `ask_price`, `last_price`: Prices (= probability %)
- `volume_24h`: 24-hour trading volume

## Data Sources

### Kalshi
- Regulated prediction market (US-based)
- API: `https://api.elections.kalshi.com/trade-api/v2`
- No authentication required for read-only access

### Polymarket
- Crypto-based prediction market
- API: `https://gamma-api.polymarket.com`
- No authentication required for read-only access

## Building Price History

To build meaningful price charts, run the ingestion script periodically:

```bash
# Manual: run every few minutes
python ingest_all.py

# Automated (Linux/Mac): add to crontab
# Run every 10 minutes
*/10 * * * * cd /path/to/prediction-pulse && python ingest_all.py --quiet
```

## Deployment to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo and select `app.py`
4. Deploy!

**Note**: SQLite on Streamlit Cloud is ephemeral (resets on redeploys). The app auto-seeds sample data on first load.

## License

MIT
