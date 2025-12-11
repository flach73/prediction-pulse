"""
Database models for Prediction Pulse.

Three-table schema:
- markets: metadata per prediction market
- contracts: the YES/NO options under each market
- prices: time-series snapshots of prices
"""

from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Market(Base):
    """A prediction market (e.g., 'Will X happen by Y date?')"""
    
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, unique=True, nullable=False, index=True)  # Kalshi's ID
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, default="open")  # open, closed, settled
    expiry_ts = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contracts = relationship("Contract", back_populates="market", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Market(market_id='{self.market_id}', title='{self.title[:30]}...')>"


class Contract(Base):
    """A tradeable contract within a market (typically YES or NO)"""
    
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, ForeignKey("markets.market_id"), nullable=False, index=True)
    contract_ticker = Column(String, unique=True, nullable=False, index=True)  # Kalshi's ticker
    side = Column(String, nullable=True)  # YES, NO, or specific outcome
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    market = relationship("Market", back_populates="contracts")
    prices = relationship("Price", back_populates="contract", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Contract(ticker='{self.contract_ticker}', side='{self.side}')>"


class Price(Base):
    """A point-in-time price snapshot for a contract"""
    
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    bid_price = Column(Float, nullable=True)  # Highest bid (cents)
    ask_price = Column(Float, nullable=True)  # Lowest ask (cents)
    last_price = Column(Float, nullable=True)  # Last trade price (cents)
    volume_24h = Column(Integer, nullable=True)  # 24h volume

    # Relationships
    contract = relationship("Contract", back_populates="prices")

    # Composite index for efficient time-series queries
    __table_args__ = (
        Index("ix_prices_contract_timestamp", "contract_id", "timestamp"),
    )

    def __repr__(self):
        return f"<Price(contract_id={self.contract_id}, last={self.last_price}, ts={self.timestamp})>"

    @property
    def implied_probability(self) -> float | None:
        """Convert last_price (in cents) to implied probability (0-100%)"""
        if self.last_price is not None:
            return self.last_price  # Kalshi prices are already in cents (0-100)
        return None


# Database connection utilities
def get_engine(db_path: str = "prediction_pulse.db"):
    """Create SQLAlchemy engine for SQLite database"""
    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_session(engine=None):
    """Create a new database session"""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(engine=None):
    """Create all tables in the database"""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine
