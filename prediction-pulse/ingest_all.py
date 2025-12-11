#!/usr/bin/env python3
"""
Ingest data from all supported prediction market sources.

Currently supports:
- Kalshi
- Polymarket

Usage:
    python ingest_all.py                # Fetch from all sources
    python ingest_all.py --kalshi-only  # Only fetch from Kalshi
    python ingest_all.py --poly-only    # Only fetch from Polymarket
    python ingest_all.py --limit 50     # Limit per source
"""

import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Ingest from all prediction market sources")
    parser.add_argument("--limit", type=int, default=50, help="Max markets per source")
    parser.add_argument("--db", type=str, default="prediction_pulse.db", help="Database path")
    parser.add_argument("--kalshi-only", action="store_true", help="Only ingest from Kalshi")
    parser.add_argument("--poly-only", action="store_true", help="Only ingest from Polymarket")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-market output")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"Prediction Pulse - Multi-Source Ingestion")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    total_stats = {
        "markets_processed": 0,
        "contracts_processed": 0,
        "prices_inserted": 0,
        "errors": [],
    }

    # Ingest from Kalshi
    if not args.poly_only:
        print("=" * 40)
        print("KALSHI")
        print("=" * 40)
        try:
            from ingest_kalshi import main as ingest_kalshi_main
            import sys
            
            # Build args for Kalshi ingestion
            kalshi_args = ["--limit", str(args.limit), "--db", args.db]
            if args.quiet:
                kalshi_args.append("--quiet")
            
            # Temporarily replace sys.argv
            old_argv = sys.argv
            sys.argv = ["ingest_kalshi.py"] + kalshi_args
            
            ingest_kalshi_main()
            
            sys.argv = old_argv
            
        except Exception as e:
            print(f"Error ingesting from Kalshi: {e}")
        print()

    # Ingest from Polymarket
    if not args.kalshi_only:
        print("=" * 40)
        print("POLYMARKET")
        print("=" * 40)
        try:
            from ingest_polymarket import main as ingest_polymarket_main
            import sys
            
            # Build args for Polymarket ingestion
            poly_args = ["--limit", str(args.limit), "--db", args.db]
            if args.quiet:
                poly_args.append("--quiet")
            
            # Temporarily replace sys.argv
            old_argv = sys.argv
            sys.argv = ["ingest_polymarket.py"] + poly_args
            
            ingest_polymarket_main()
            
            sys.argv = old_argv
            
        except Exception as e:
            print(f"Error ingesting from Polymarket: {e}")
        print()

    print(f"{'='*60}")
    print(f"All ingestion complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
