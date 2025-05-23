from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class OrderBook(Base):
    __tablename__ = 'orderbook'

    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    asset_id = Column(String)
    market = Column(String)
    best_bid = Column(Float, nullable=True)
    bid_size = Column(Float, nullable=True)
    best_ask = Column(Float, nullable=True)
    ask_size = Column(Float, nullable=True)
    mid_price = Column(Float, nullable=True)
    spread = Column(Float, nullable=True)
    timestamp = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class PriceChange(Base):
    __tablename__ = 'price_changes'
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    asset_id = Column(String)
    market = Column(String)
    price = Column(String)
    size = Column(String)
    side = Column(String)
    timestamp = Column(String)
    hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class TickSizeChange(Base):
    __tablename__ = 'tick_size_changes'
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    asset_id = Column(String)
    market = Column(String)
    old_tick_size = Column(String)
    new_tick_size = Column(String)
    timestamp = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create database engine and session
engine = create_engine('sqlite:///poly-starter-code/market_data.db')
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine) 