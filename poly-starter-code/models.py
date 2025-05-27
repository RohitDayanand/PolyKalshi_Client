from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the root .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get database configuration from environment variables
DB_USER = os.getenv('POSTGRES_USER', 'myuser')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'mypassword')
DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'mytradingdb')

Base = declarative_base()

class OrderBook(Base):
    __tablename__ = 'poly_orderbook'
    __table_args__ = {'schema': 'polymarket'}

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
    __tablename__ = 'poly_price_changes'
    __table_args__ = {'schema': 'polymarket'}
    
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
    __tablename__ = 'poly_tick_size_changes'
    __table_args__ = {'schema': 'polymarket'}
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    asset_id = Column(String)
    market = Column(String)
    old_tick_size = Column(String)
    new_tick_size = Column(String)
    timestamp = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create database engine and session with PostgreSQL
DATABASE_URL = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """Initialize database tables if they don't exist."""
    try:
        # Create schema if it doesn't exist
        '''
        connection = engine.connect()
        connection.execute("CREATE SCHEMA IF NOT EXISTS polymarket;")
        connection.close()
        '''
        # Create tables
        Base.metadata.create_all(engine)
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

#Create tables if they do not exist

init_db()