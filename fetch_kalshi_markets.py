#!/usr/bin/env python3
"""
Fetch markets from Kalshi's public API.

This script demonstrates how to:
1. Call Kalshi's public market endpoints
2. Filter for specific categories
3. Parse and display market data

Usage:
    python fetch_kalshi_markets.py
    python fetch_kalshi_markets.py --category politics
    python fetch_kalshi_markets.py --limit 20
"""

import argparse
import requests
from datetime import datetime
from typing import Any


# Kalshi API base URL (public, no auth required for reading)
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# Alternative base URL if the elections one doesn't work
KALSHI_API_BASE_ALT = "https://trading-api.kalshi.com/trade-api/v2"


def fetch_events(limit: int = 100, status: str = "open", cursor: str = None) -> dict:
    """
    Fetch events (market groups) from Kalshi.
    
    Events are containers for related markets (e.g., "2024 Presidential Election"
    contains markets for each state).
    """
    url = f"{KALSHI_API_BASE}/events"
    params = {
        "limit": limit,
        "status": status,
    }
    if cursor:
        params["cursor"] = cursor
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_markets(
    limit: int = 100,
    status: str = "open",
    cursor: str = None,
    event_ticker: str = None,
) -> dict:
    """
    Fetch markets from Kalshi.
    
    A market is a single yes/no question with a specific resolution date.
    """
    url = f"{KALSHI_API_BASE}/markets"
    params = {
        "limit": limit,
        "status": status,
    }
    if cursor:
        params["cursor"] = cursor
    if event_ticker:
        params["event_ticker"] = event_ticker
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_market_detail(ticker: str) -> dict:
    """Fetch detailed info for a specific market by ticker."""
    url = f"{KALSHI_API_BASE}/markets/{ticker}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_market(raw: dict) -> dict:
    """
    Parse a raw Kalshi market response into a cleaner format.
    
    Kalshi prices are in cents (0-100), which directly represent probability %.
    """
    # Extract close time
    close_time = raw.get("close_time") or raw.get("expiration_time")
    if close_time:
        try:
            expiry = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            expiry = None
    else:
        expiry = None

    return {
        "ticker": raw.get("ticker"),
        "event_ticker": raw.get("event_ticker"),
        "title": raw.get("title") or raw.get("subtitle"),
        "category": raw.get("category"),
        "status": raw.get("status"),
        "expiry": expiry,
        # Price data (in cents = probability %)
        "yes_bid": raw.get("yes_bid"),
        "yes_ask": raw.get("yes_ask"),
        "last_price": raw.get("last_price"),
        "volume": raw.get("volume"),
        "volume_24h": raw.get("volume_24h"),
        # Additional metadata
        "open_interest": raw.get("open_interest"),
        "result": raw.get("result"),
    }


def filter_markets(
    markets: list[dict],
    category: str = None,
    min_volume: int = None,
    future_only: bool = True,
) -> list[dict]:
    """Filter markets by category, volume, and expiration."""
    filtered = []
    now = datetime.now().astimezone()
    
    for m in markets:
        # Category filter
        if category:
            market_category = (m.get("category") or "").lower()
            if category.lower() not in market_category:
                continue
        
        # Volume filter
        if min_volume:
            vol = m.get("volume") or m.get("volume_24h") or 0
            if vol < min_volume:
                continue
        
        # Future expiry filter
        if future_only and m.get("expiry"):
            if m["expiry"].replace(tzinfo=None) < now.replace(tzinfo=None):
                continue
        
        filtered.append(m)
    
    return filtered


def display_markets(markets: list[dict], detailed: bool = False):
    """Pretty print market information."""
    print(f"\n{'='*80}")
    print(f"Found {len(markets)} markets")
    print(f"{'='*80}\n")
    
    for i, m in enumerate(markets, 1):
        prob = m.get("last_price") or m.get("yes_bid") or "N/A"
        if isinstance(prob, (int, float)):
            prob_str = f"{prob:.0f}%"
        else:
            prob_str = prob
            
        expiry = m.get("expiry")
        expiry_str = expiry.strftime("%Y-%m-%d") if expiry else "N/A"
        
        print(f"{i:3}. [{m.get('ticker', 'N/A'):20}] {prob_str:>5} | {m.get('title', 'No title')[:50]}")
        
        if detailed:
            print(f"     Category: {m.get('category', 'N/A')}")
            print(f"     Expiry: {expiry_str}")
            print(f"     Volume 24h: {m.get('volume_24h', 'N/A')}")
            print(f"     Bid/Ask: {m.get('yes_bid', 'N/A')}/{m.get('yes_ask', 'N/A')}")
            print()


def main():
    parser = argparse.ArgumentParser(description="Fetch Kalshi prediction markets")
    parser.add_argument("--limit", type=int, default=50, help="Number of markets to fetch")
    parser.add_argument("--category", type=str, help="Filter by category (e.g., 'politics')")
    parser.add_argument("--min-volume", type=int, help="Minimum 24h volume")
    parser.add_argument("--detailed", action="store_true", help="Show detailed market info")
    parser.add_argument("--include-expired", action="store_true", help="Include expired markets")
    args = parser.parse_args()

    print("Fetching markets from Kalshi...")
    
    try:
        # Fetch raw markets
        response = fetch_markets(limit=args.limit, status="open")
        raw_markets = response.get("markets", [])
        
        print(f"Fetched {len(raw_markets)} raw markets from API")
        
        # Parse into cleaner format
        parsed = [parse_market(m) for m in raw_markets]
        
        # Apply filters
        filtered = filter_markets(
            parsed,
            category=args.category,
            min_volume=args.min_volume,
            future_only=not args.include_expired,
        )
        
        # Display
        display_markets(filtered, detailed=args.detailed)
        
        # Return for use in other scripts
        return filtered
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Kalshi API: {e}")
        print("\nTrying alternative API base URL...")
        
        # Try alternative URL
        global KALSHI_API_BASE
        KALSHI_API_BASE = KALSHI_API_BASE_ALT
        
        try:
            response = fetch_markets(limit=args.limit, status="open")
            raw_markets = response.get("markets", [])
            parsed = [parse_market(m) for m in raw_markets]
            filtered = filter_markets(
                parsed,
                category=args.category,
                min_volume=args.min_volume,
                future_only=not args.include_expired,
            )
            display_markets(filtered, detailed=args.detailed)
            return filtered
        except Exception as e2:
            print(f"Alternative URL also failed: {e2}")
            return []


if __name__ == "__main__":
    main()
