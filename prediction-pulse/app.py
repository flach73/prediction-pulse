#!/usr/bin/env python3
"""
Prediction Pulse Dashboard

A Streamlit app that displays prediction market data from the local database.

Features:
- Table of current markets with implied probabilities
- Filter by category and expiration
- Click to see price history charts
- Auto-refresh option

Usage:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc

from db import get_engine, get_session, init_db, Market, Contract, Price


# Page config
st.set_page_config(
    page_title="Prediction Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_db_session():
    """Get a cached database session."""
    import os
    db_path = os.path.join(os.path.dirname(__file__), "prediction_pulse.db")
    engine = get_engine(db_path)
    init_db(engine)
    
    # Auto-seed if database is empty
    session = get_session(engine)
    market_count = session.query(Market).count()
    if market_count == 0:
        session.close()
        from seed_sample_data import seed_database
        seed_database(db_path)
        session = get_session(engine)
    
    return session


def load_markets_with_prices(session, category: str = None, status: str = "open") -> pd.DataFrame:
    """Load all markets with their latest price data."""
    
    # Subquery to get latest price per contract
    latest_price_subq = (
        select(
            Price.contract_id,
            func.max(Price.timestamp).label("max_ts")
        )
        .group_by(Price.contract_id)
        .subquery()
    )
    
    # Main query joining markets, contracts, and latest prices
    query = (
        select(
            Market.market_id,
            Market.title,
            Market.category,
            Market.status,
            Market.expiry_ts,
            Market.updated_at,
            Contract.contract_ticker,
            Contract.side,
            Price.last_price,
            Price.bid_price,
            Price.ask_price,
            Price.volume_24h,
            Price.timestamp.label("price_timestamp"),
        )
        .join(Contract, Contract.market_id == Market.market_id)
        .join(latest_price_subq, Contract.id == latest_price_subq.c.contract_id)
        .join(Price, (Price.contract_id == Contract.id) & (Price.timestamp == latest_price_subq.c.max_ts))
    )
    
    # Apply filters
    if status:
        query = query.where(Market.status == status)
    if category and category != "All":
        query = query.where(Market.category.ilike(f"%{category}%"))
    
    query = query.order_by(desc(Price.volume_24h))
    
    result = session.execute(query)
    
    # Convert to DataFrame
    df = pd.DataFrame(result.fetchall())
    if len(df) == 0:
        return pd.DataFrame()
    
    df.columns = [
        "market_id", "title", "category", "status", "expiry_ts", "updated_at",
        "contract_ticker", "side", "last_price", "bid_price", "ask_price", 
        "volume_24h", "price_timestamp"
    ]
    
    return df


def load_price_history(session, contract_ticker: str, days: int = 7) -> pd.DataFrame:
    """Load price history for a specific contract."""
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = (
        select(
            Price.timestamp,
            Price.last_price,
            Price.bid_price,
            Price.ask_price,
            Price.volume_24h,
        )
        .join(Contract, Contract.id == Price.contract_id)
        .where(Contract.contract_ticker == contract_ticker)
        .where(Price.timestamp >= cutoff)
        .order_by(Price.timestamp)
    )
    
    result = session.execute(query)
    df = pd.DataFrame(result.fetchall())
    
    if len(df) == 0:
        return pd.DataFrame()
    
    df.columns = ["timestamp", "last_price", "bid_price", "ask_price", "volume_24h"]
    return df


def get_categories(session) -> list[str]:
    """Get unique categories from database."""
    query = select(Market.category).distinct().where(Market.category.isnot(None))
    result = session.execute(query)
    categories = [r[0] for r in result.fetchall() if r[0]]
    return ["All"] + sorted(categories)


def render_sidebar(session):
    """Render the sidebar with filters."""
    st.sidebar.title("🎯 Prediction Pulse")
    st.sidebar.markdown("---")
    
    # Category filter
    categories = get_categories(session)
    selected_category = st.sidebar.selectbox(
        "Category",
        options=categories,
        index=0,
    )
    
    # Status filter
    show_open_only = st.sidebar.checkbox("Open markets only", value=True)
    status = "open" if show_open_only else None
    
    # Future expiry filter
    future_only = st.sidebar.checkbox("Future expiry only", value=True)
    
    # Refresh button
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Info
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Data from Kalshi prediction markets. "
        "Prices represent implied probability (0-100%)."
    )
    
    return {
        "category": selected_category,
        "status": status,
        "future_only": future_only,
    }


def render_market_table(df: pd.DataFrame) -> str | None:
    """Render the main markets table. Returns selected market ticker."""
    
    if df.empty:
        st.warning("No markets found. Run the ingestion script first:")
        st.code("python ingest_kalshi.py")
        return None
    
    # Prepare display dataframe
    display_df = df.copy()
    
    # Format columns
    display_df["Probability"] = display_df["last_price"].apply(
        lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A"
    )
    display_df["Bid/Ask"] = display_df.apply(
        lambda r: f"{r['bid_price']:.0f}/{r['ask_price']:.0f}" 
        if pd.notna(r['bid_price']) and pd.notna(r['ask_price']) 
        else "N/A",
        axis=1
    )
    display_df["Volume (24h)"] = display_df["volume_24h"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["Expiry"] = display_df["expiry_ts"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "N/A"
    )
    
    # Select columns for display
    table_df = display_df[[
        "title", "Probability", "Bid/Ask", "Volume (24h)", "Expiry", "category", "contract_ticker"
    ]].rename(columns={
        "title": "Market",
        "category": "Category",
        "contract_ticker": "Ticker"
    })
    
    # Show table with selection
    st.subheader(f"📈 Markets ({len(table_df)})")
    
    # Use data editor for selection
    selected = st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Market": st.column_config.TextColumn("Market", width="large"),
            "Probability": st.column_config.TextColumn("Prob", width="small"),
            "Bid/Ask": st.column_config.TextColumn("Bid/Ask", width="small"),
            "Volume (24h)": st.column_config.TextColumn("Vol 24h", width="small"),
            "Expiry": st.column_config.TextColumn("Expiry", width="small"),
            "Category": st.column_config.TextColumn("Category", width="medium"),
            "Ticker": st.column_config.TextColumn("Ticker", width="medium"),
        },
        height=400,
    )
    
    # Market selector dropdown
    st.markdown("---")
    ticker_options = ["Select a market..."] + display_df["contract_ticker"].tolist()
    selected_ticker = st.selectbox(
        "Select market to view price history:",
        options=ticker_options,
        format_func=lambda x: x if x == "Select a market..." else f"{x} - {display_df[display_df['contract_ticker']==x]['title'].iloc[0][:50]}..."
    )
    
    if selected_ticker != "Select a market...":
        return selected_ticker
    return None


def render_price_chart(session, ticker: str, market_title: str):
    """Render price history chart for a market."""
    
    st.subheader(f"📊 Price History: {market_title[:60]}...")
    
    # Time range selector
    days = st.selectbox("Time range", [1, 7, 14, 30], index=1, format_func=lambda x: f"{x} day{'s' if x > 1 else ''}")
    
    # Load data
    df = load_price_history(session, ticker, days=days)
    
    if df.empty:
        st.info("No price history available for this market yet. Run the ingestion script multiple times to build history.")
        return
    
    # Create chart
    fig = go.Figure()
    
    # Add last price line
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["last_price"],
        mode="lines+markers",
        name="Last Price",
        line=dict(color="#00D4AA", width=2),
        marker=dict(size=6),
    ))
    
    # Add bid/ask spread as filled area
    if df["bid_price"].notna().any() and df["ask_price"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["ask_price"],
            mode="lines",
            name="Ask",
            line=dict(color="rgba(255,100,100,0.3)", width=1),
        ))
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["bid_price"],
            mode="lines",
            name="Bid",
            line=dict(color="rgba(100,255,100,0.3)", width=1),
            fill="tonexty",
            fillcolor="rgba(200,200,200,0.2)",
        ))
    
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Implied Probability (%)",
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        current = df["last_price"].iloc[-1] if len(df) > 0 else None
        st.metric("Current", f"{current:.1f}%" if current else "N/A")
    with col2:
        high = df["last_price"].max()
        st.metric("High", f"{high:.1f}%" if pd.notna(high) else "N/A")
    with col3:
        low = df["last_price"].min()
        st.metric("Low", f"{low:.1f}%" if pd.notna(low) else "N/A")
    with col4:
        if len(df) > 1:
            change = df["last_price"].iloc[-1] - df["last_price"].iloc[0]
            st.metric("Change", f"{change:+.1f}%")
        else:
            st.metric("Change", "N/A")


def main():
    """Main dashboard entry point."""
    
    # Get database session
    session = get_db_session()
    
    # Render sidebar and get filters
    filters = render_sidebar(session)
    
    # Main content
    st.title("Prediction Pulse")
    st.caption("Real-time prediction market data from Kalshi")
    
    # Load and display markets
    df = load_markets_with_prices(
        session,
        category=filters["category"],
        status=filters["status"],
    )
    
    # Filter by future expiry if selected
    if filters["future_only"] and not df.empty:
        now = datetime.utcnow()
        df = df[df["expiry_ts"].isna() | (df["expiry_ts"] > now)]
    
    # Show market table and get selection
    selected_ticker = render_market_table(df)
    
    # Show price chart if market selected
    if selected_ticker and not df.empty:
        market_row = df[df["contract_ticker"] == selected_ticker].iloc[0]
        render_price_chart(session, selected_ticker, market_row["title"])


if __name__ == "__main__":
    main()
