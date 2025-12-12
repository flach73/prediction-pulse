#!/usr/bin/env python3
"""
Seed the database with sample data for testing/demo purposes.

Run this if you can't access the APIs or want to demo the dashboard
without waiting for real data to accumulate.

Usage:
    python seed_sample_data.py
"""

from datetime import datetime, timedelta, timezone
import random

from db import get_engine, get_session, init_db, Market, Contract, Price


def utcnow():
    return datetime.now(timezone.utc)


SAMPLE_MARKETS = [
    # Kalshi-style markets
    {
        "market_id": "FED-RATE-DEC-25",
        "source": "kalshi",
        "title": "Will the Fed cut rates in December 2025?",
        "category": "Economics",
        "expiry_days": 30,
        "base_prob": 65,
    },
    {
        "market_id": "TRUMP-APPROVAL-50",
        "source": "kalshi",
        "title": "Will Trump approval rating exceed 50% by March?",
        "category": "Politics",
        "expiry_days": 90,
        "base_prob": 35,
    },
    {
        "market_id": "GDP-GROWTH-Q1",
        "source": "kalshi",
        "title": "Will Q1 2026 GDP growth exceed 2%?",
        "category": "Economics",
        "expiry_days": 120,
        "base_prob": 48,
    },
    {
        "market_id": "SCOTUS-RULING-JAN",
        "source": "kalshi",
        "title": "Will SCOTUS rule on immigration case by January?",
        "category": "Politics",
        "expiry_days": 45,
        "base_prob": 72,
    },
    # Polymarket-style markets
    {
        "market_id": "poly_btc-100k-2025",
        "source": "polymarket",
        "title": "Will Bitcoin reach $100,000 in 2025?",
        "category": "Crypto",
        "expiry_days": 365,
        "base_prob": 55,
    },
    {
        "market_id": "poly_eth-merge-success",
        "source": "polymarket",
        "title": "Will Ethereum stay above $3,000 through Q1?",
        "category": "Crypto",
        "expiry_days": 100,
        "base_prob": 62,
    },
    {
        "market_id": "poly_sp500-5500",
        "source": "polymarket",
        "title": "Will S&P 500 close above 5,500 by end of January?",
        "category": "Markets",
        "expiry_days": 50,
        "base_prob": 60,
    },
    {
        "market_id": "poly_unemployment",
        "source": "polymarket",
        "title": "Will unemployment rate stay below 4% through Q1?",
        "category": "Economics",
        "expiry_days": 100,
        "base_prob": 68,
    },
]


def generate_price_history(base_prob: float, days: int = 7, points_per_day: int = 6) -> list[dict]:
    """Generate realistic-looking price history with random walk."""
    prices = []
    current_prob = base_prob + random.uniform(-10, 10)
    
    now = utcnow()
    total_points = days * points_per_day
    
    for i in range(total_points):
        # Random walk with mean reversion
        drift = (base_prob - current_prob) * 0.05  # Pull toward base
        noise = random.gauss(0, 2)  # Random noise
        current_prob = max(1, min(99, current_prob + drift + noise))
        
        timestamp = now - timedelta(hours=(total_points - i) * (24 / points_per_day))
        
        # Generate bid/ask around last price
        spread = random.uniform(1, 3)
        bid = max(1, current_prob - spread / 2)
        ask = min(99, current_prob + spread / 2)
        
        prices.append({
            "timestamp": timestamp,
            "last_price": round(current_prob, 1),
            "bid_price": round(bid, 1),
            "ask_price": round(ask, 1),
            "volume_24h": random.randint(1000, 50000),
        })
    
    return prices


def seed_database(db_path: str = "prediction_pulse.db"):
    """Seed the database with sample markets and price history."""
    
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    
    print("Seeding database with sample data...")
    print()
    
    try:
        for m in SAMPLE_MARKETS:
            # Create market
            market = Market(
                market_id=m["market_id"],
                source=m["source"],
                title=m["title"],
                category=m["category"],
                status="open",
                expiry_ts=utcnow() + timedelta(days=m["expiry_days"]),
            )
            session.merge(market)
            session.flush()
            
            # Create contract
            contract_ticker = m["market_id"] if m["source"] == "kalshi" else f"{m['market_id']}_YES"
            contract = Contract(
                market_id=m["market_id"],
                contract_ticker=contract_ticker,
                side="YES",
                description=f"YES contract for {m['title'][:30]}...",
            )
            session.merge(contract)
            session.flush()
            
            # Get contract ID for prices
            contract = session.query(Contract).filter_by(contract_ticker=contract_ticker).first()
            
            # Generate and insert price history
            prices = generate_price_history(m["base_prob"])
            for p in prices:
                price = Price(
                    contract_id=contract.id,
                    timestamp=p["timestamp"],
                    last_price=p["last_price"],
                    bid_price=p["bid_price"],
                    ask_price=p["ask_price"],
                    volume_24h=p["volume_24h"],
                )
                session.add(price)
            
            source_label = m["source"].capitalize()
            print(f"  [{source_label}] {m['market_id']}: {m['title'][:35]}... ({len(prices)} price points)")
        
        session.commit()
        print()
        print(f"Seeded {len(SAMPLE_MARKETS)} markets with price history")
        print()
        print("You can now run the dashboard:")
        print("  streamlit run app.py")
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
