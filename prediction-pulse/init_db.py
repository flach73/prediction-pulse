#!/usr/bin/env python3
"""
Initialize the Prediction Pulse database.

Run this script once to create the SQLite database and tables:
    python init_db.py

The database file (prediction_pulse.db) will be created in the current directory.
"""

from db import init_db, get_engine

def main():
    print("Initializing Prediction Pulse database...")
    
    engine = get_engine("prediction_pulse.db")
    init_db(engine)
    
    print("✓ Database created: prediction_pulse.db")
    print("✓ Tables created: markets, contracts, prices")
    print("\nYou can now run the ingestion script:")
    print("  python ingest_kalshi.py")

if __name__ == "__main__":
    main()
