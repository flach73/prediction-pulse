#!/usr/bin/env python3
"""
Fetch markets from Polymarket's public API.

Polymarket uses the Gamma API for public market data.

Usage:
    python fetch_polymarket.py
    python fetch_polymarket.py --limit 50
    python fetch_polymarket.py --active-only
"""

import argparse
import requests
from datetime import datetime
from typing import Any


# Polymarket Gamma API base URL
POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"


def fetch_markets(
    limit: int = 100,
    offset: int = 0,
    active: bool = True,
    closed: bool = False,
) -> list[dict]:
    """
    Fetch markets from Polymarket.
    
    Returns a list of market objects.
    """
    url = f"{POLYMARKET_API_BASE}/markets"
    params = {
        "limit": limit,
        "offset": offset,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
    }
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_market_detail(condition_id: str) -> dict:
    """Fetch detailed info for a specific market."""
    url = f"{POLYMARKET_API_BASE}/markets/{condition_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_market(raw: dict) -> dict:
    """
    Parse a raw Polymarket market response into a cleaner format.
    
    Polymarket prices are decimals 0-1, we convert to 0-100 for consistency.
    """
    # Parse end date
    end_date = raw.get("endDate") or raw.get("end_date_iso")
    if end_date:
        try:
            if isinstance(end_date, str):
                # Handle various date formats
                end_date = end_date.replace("Z", "+00:00")
                expiry = datetime.fromisoformat(end_date)
            else:
                expiry = None
        except (ValueError, TypeError):
            expiry = None
    else:
        expiry = None

    # Get price - Polymarket uses outcomePrices as a JSON string like "[\"0.5\", \"0.5\"]"
    # or has a separate price field
    outcome_prices = raw.get("outcomePrices")
    if outcome_prices:
        try:
            if isinstance(outcome_prices, str):
                import json
                prices = json.loads(outcome_prices)
                yes_price = float(prices[0]) * 100  # Convert to percentage
            else:
                yes_price = float(outcome_prices[0]) * 100
        except (json.JSONDecodeError, IndexError, TypeError, ValueError):
            yes_price = None
    else:
        # Try bestAsk/bestBid fields
        yes_price = raw.get("bestAsk") or raw.get("lastTradePrice")
        if yes_price:
            yes_price = float(yes_price) * 100

    # Get volume
    volume = raw.get("volume") or raw.get("volumeNum")
    if volume:
        try:
            volume = int(float(volume))
        except (ValueError, TypeError):
            volume = None

    return {
        "condition_id": raw.get("conditionId") or raw.get("condition_id"),
        "question_id": raw.get("questionId") or raw.get("question_id"),
        "slug": raw.get("slug"),
        "title": raw.get("question") or raw.get("title"),
        "category": raw.get("category") or extract_category(raw.get("tags", [])),
        "status": "open" if raw.get("active") else "closed",
        "expiry": expiry,
        "yes_price": yes_price,
        "volume": volume,
        "liquidity": raw.get("liquidity"),
        "outcomes": raw.get("outcomes"),
    }


def extract_category(tags: list) -> str | None:
    """Extract a category from tags list."""
    if not tags:
        return None
    # Common category tags
    category_keywords = ["politics", "crypto", "sports", "science", "entertainment", "economics"]
    for tag in tags:
        tag_lower = tag.lower() if isinstance(tag, str) else ""
        for keyword in category_keywords:
            if keyword in tag_lower:
                return keyword.capitalize()
    return tags[0] if tags else None


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
        # Skip markets without essential data
        if not m.get("condition_id") or not m.get("title"):
            continue
            
        # Category filter
        if category:
            market_category = (m.get("category") or "").lower()
            if category.lower() not in market_category:
                continue
        
        # Volume filter
        if min_volume:
            vol = m.get("volume") or 0
            if vol < min_volume:
                continue
        
        # Future expiry filter
        if future_only and m.get("expiry"):
            try:
                expiry = m["expiry"]
                if hasattr(expiry, 'replace'):
                    if expiry.replace(tzinfo=None) < now.replace(tzinfo=None):
                        continue
            except:
                pass
        
        filtered.append(m)
    
    return filtered


def display_markets(markets: list[dict], detailed: bool = False):
    """Pretty print market information."""
    print(f"\n{'='*80}")
    print(f"Found {len(markets)} markets from Polymarket")
    print(f"{'='*80}\n")
    
    for i, m in enumerate(markets, 1):
        prob = m.get("yes_price")
        if prob is not None:
            prob_str = f"{prob:.0f}%"
        else:
            prob_str = "N/A"
            
        expiry = m.get("expiry")
        expiry_str = expiry.strftime("%Y-%m-%d") if expiry else "N/A"
        
        title = m.get("title", "No title")[:50]
        condition_id = m.get("condition_id", "N/A")[:20]
        
        print(f"{i:3}. [{condition_id:20}] {prob_str:>5} | {title}")
        
        if detailed:
            print(f"     Category: {m.get('category', 'N/A')}")
            print(f"     Expiry: {expiry_str}")
            print(f"     Volume: ${m.get('volume', 'N/A'):,}" if m.get('volume') else "     Volume: N/A")
            print()


def main():
    parser = argparse.ArgumentParser(description="Fetch Polymarket prediction markets")
    parser.add_argument("--limit", type=int, default=50, help="Number of markets to fetch")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--min-volume", type=int, help="Minimum volume")
    parser.add_argument("--detailed", action="store_true", help="Show detailed market info")
    parser.add_argument("--include-closed", action="store_true", help="Include closed markets")
    args = parser.parse_args()

    print("Fetching markets from Polymarket...")
    
    try:
        # Fetch raw markets
        raw_markets = fetch_markets(
            limit=args.limit,
            active=not args.include_closed,
        )
        
        print(f"Fetched {len(raw_markets)} raw markets from API")
        
        # Parse into cleaner format
        parsed = [parse_market(m) for m in raw_markets]
        
        # Apply filters
        filtered = filter_markets(
            parsed,
            category=args.category,
            min_volume=args.min_volume,
            future_only=not args.include_closed,
        )
        
        # Display
        display_markets(filtered, detailed=args.detailed)
        
        return filtered
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Polymarket API: {e}")
        return []


if __name__ == "__main__":
    main()
