#!/usr/bin/env python3
"""
Ingest Kalshi market data into the local database.

This ETL script:
1. Fetches markets from Kalshi API
2. Upserts market and contract metadata
3. Inserts price snapshots for time-series tracking

Usage:
    python ingest_kalshi.py                    # Fetch all open markets
    python ingest_kalshi.py --category politics # Filter by category
    python ingest_kalshi.py --limit 100        # Limit number of markets

Run this periodically (e.g., every 5-10 minutes) to build price history.
"""

import argparse
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from db import get_engine, get_session, init_db, Market, Contract, Price
from fetch_kalshi_markets import fetch_markets, parse_market, filter_markets


def upsert_market(session, market_data: dict) -> Market:
    """Insert or update a market record."""
    stmt = sqlite_upsert(Market).values(
        market_id=market_data["ticker"],
        title=market_data["title"],
        category=market_data.get("category"),
        status=market_data.get("status", "open"),
        expiry_ts=market_data.get("expiry"),
        updated_at=datetime.utcnow(),
    )
    
    # On conflict, update everything except created_at
    stmt = stmt.on_conflict_do_update(
        index_elements=["market_id"],
        set_={
            "title": stmt.excluded.title,
            "category": stmt.excluded.category,
            "status": stmt.excluded.status,
            "expiry_ts": stmt.excluded.expiry_ts,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    session.execute(stmt)
    session.flush()
    
    # Return the market object
    return session.execute(
        select(Market).where(Market.market_id == market_data["ticker"])
    ).scalar_one()


def upsert_contract(session, market_id: str, ticker: str, side: str = "YES") -> Contract:
    """Insert or update a contract record."""
    stmt = sqlite_upsert(Contract).values(
        market_id=market_id,
        contract_ticker=ticker,
        side=side,
        description=f"{side} contract for {market_id}",
    )
    
    stmt = stmt.on_conflict_do_update(
        index_elements=["contract_ticker"],
        set_={
            "side": stmt.excluded.side,
            "description": stmt.excluded.description,
        }
    )
    
    session.execute(stmt)
    session.flush()
    
    return session.execute(
        select(Contract).where(Contract.contract_ticker == ticker)
    ).scalar_one()


def insert_price_snapshot(
    session,
    contract_id: int,
    bid: Optional[float],
    ask: Optional[float],
    last: Optional[float],
    volume_24h: Optional[int],
) -> Price:
    """Insert a new price snapshot."""
    price = Price(
        contract_id=contract_id,
        timestamp=datetime.utcnow(),
        bid_price=bid,
        ask_price=ask,
        last_price=last,
        volume_24h=volume_24h,
    )
    session.add(price)
    return price


def ingest_markets(
    markets: list[dict],
    db_path: str = "prediction_pulse.db",
    verbose: bool = True,
) -> dict:
    """
    Ingest a list of parsed markets into the database.
    
    Returns stats about what was ingested.
    """
    engine = get_engine(db_path)
    init_db(engine)  # Ensure tables exist
    session = get_session(engine)
    
    stats = {
        "markets_processed": 0,
        "contracts_processed": 0,
        "prices_inserted": 0,
        "errors": [],
    }
    
    try:
        for m in markets:
            ticker = m.get("ticker")
            if not ticker:
                continue
                
            try:
                # Upsert market
                market = upsert_market(session, m)
                stats["markets_processed"] += 1
                
                # For Kalshi, each market has a YES contract
                # The ticker is the contract ticker
                contract = upsert_contract(
                    session,
                    market_id=market.market_id,
                    ticker=ticker,
                    side="YES",
                )
                stats["contracts_processed"] += 1
                
                # Insert price snapshot
                price = insert_price_snapshot(
                    session,
                    contract_id=contract.id,
                    bid=m.get("yes_bid"),
                    ask=m.get("yes_ask"),
                    last=m.get("last_price"),
                    volume_24h=m.get("volume_24h"),
                )
                stats["prices_inserted"] += 1
                
                if verbose:
                    prob = m.get("last_price", "N/A")
                    print(f"  ✓ {ticker}: {prob}%")
                    
            except Exception as e:
                stats["errors"].append(f"{ticker}: {str(e)}")
                if verbose:
                    print(f"  ✗ {ticker}: {e}")
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    
    return stats


def print_summary(stats: dict):
    """Print ingestion summary."""
    print(f"\n{'='*50}")
    print("Ingestion Summary")
    print(f"{'='*50}")
    print(f"Markets processed:  {stats['markets_processed']}")
    print(f"Contracts processed: {stats['contracts_processed']}")
    print(f"Price snapshots:    {stats['prices_inserted']}")
    
    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"][:5]:
            print(f"  - {err}")
        if len(stats["errors"]) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")


def main():
    parser = argparse.ArgumentParser(description="Ingest Kalshi data into database")
    parser.add_argument("--limit", type=int, default=100, help="Max markets to fetch")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--min-volume", type=int, help="Minimum 24h volume")
    parser.add_argument("--db", type=str, default="prediction_pulse.db", help="Database path")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-market output")
    args = parser.parse_args()

    print(f"Starting Kalshi ingestion at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {args.db}")
    print()

    # Fetch from API
    print("Fetching markets from Kalshi API...")
    try:
        response = fetch_markets(limit=args.limit, status="open")
        raw_markets = response.get("markets", [])
        print(f"Fetched {len(raw_markets)} markets from API")
    except Exception as e:
        print(f"Error fetching from API: {e}")
        return

    # Parse and filter
    parsed = [parse_market(m) for m in raw_markets]
    filtered = filter_markets(
        parsed,
        category=args.category,
        min_volume=args.min_volume,
        future_only=True,
    )
    print(f"After filtering: {len(filtered)} markets")
    print()

    # Ingest
    print("Ingesting into database...")
    stats = ingest_markets(filtered, db_path=args.db, verbose=not args.quiet)
    
    print_summary(stats)
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
