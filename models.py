from sqlalchemy import create_engine, Column, Integer, String, Boolean, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class KalshiOrderbookSnapshot(Base):
    __tablename__ = 'kalshi_orderbook_snapshots'
    id = Column(Integer, primary_key=True)
    market_ticker = Column(String)
    sid = Column(Integer)
    seq = Column(Integer)
    timestamp = Column(String)
    yes_orders = Column(String)
    no_orders = Column(String)
    created_at = Column(TIMESTAMP)

class KalshiOrderbookDelta(Base):
    __tablename__ = 'kalshi_orderbook_deltas'
    id = Column(Integer, primary_key=True)
    market_ticker = Column(String)
    sid = Column(Integer)
    seq = Column(Integer)
    timestamp = Column(String)
    price_cents = Column(Integer)
    delta = Column(Integer)
    side = Column(String)
    created_at = Column(TIMESTAMP)

class KalshiOrderbookTrade(Base):
    __tablename__ = 'kalshi_orderbook_trades'
    id = Column(Integer, primary_key=True)
    market_ticker = Column(String)
    sid = Column(Integer)
    yes_price = Column(Integer)
    no_price = Column(Integer)
    count = Column(Integer)
    taker_side = Column(String)
    ts = Column(Integer)
    received_at = Column(TIMESTAMP)

class KalshiOrderbookFill(Base):
    __tablename__ = 'kalshi_orderbook_fills'
    id = Column(Integer, primary_key=True)
    trade_id = Column(String)
    order_id = Column(String)
    market_ticker = Column(String)
    sid = Column(Integer)
    is_taker = Column(Boolean)
    side = Column(String)
    yes_price = Column(Integer)
    no_price = Column(Integer)
    count = Column(Integer)
    action = Column(String)
    ts = Column(Integer)
    received_at = Column(TIMESTAMP)

class KalshiOrderbookTickerV2(Base):
    __tablename__ = 'kalshi_orderbook_ticker_v2'
    id = Column(Integer, primary_key=True)
    market_ticker = Column(String)
    sid = Column(Integer)
    price = Column(Integer)
    yes_bid = Column(Integer)
    yes_ask = Column(Integer)
    volume_delta = Column(Integer)
    open_interest_delta = Column(Integer)
    dollar_volume_delta = Column(Integer)
    dollar_open_interest_delta = Column(Integer)
    ts = Column(Integer)
    received_at = Column(TIMESTAMP)

# Database setup
DATABASE_URL = "postgresql+psycopg2://myuser:mypassword@localhost/mytradingdb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine) 