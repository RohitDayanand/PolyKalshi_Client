from sqlalchemy import Column, String, Float, DateTime, Integer, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, AsyncGenerator

# Load environment variables from the root .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get database configuration from environment variables
DB_USER = os.getenv('POSTGRES_USER', 'myuser')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'mypassword')
DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'mytradingdb')

# SQLAlchemy 2.0 declarative base
class Base(DeclarativeBase):
    """Base class for all database models using SQLAlchemy 2.0 syntax."""
    pass

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

# Async PostgreSQL database configuration
ASYNC_DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Create async engine with optimized connection pooling
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,          # Base pool size for concurrent connections
    max_overflow=30,       # Additional connections during peak load
    pool_pre_ping=True,    # Validate connections before use
    pool_recycle=3600,     # Recycle connections every hour
    echo=False,            # Set to True for SQL debugging
    connect_args={
        "server_settings": {
            "jit": "off"   # Disable JIT for better performance with many short queries
        }
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
    autoflush=False,         # Manual flushing for better control
    autocommit=False         # Explicit transaction control
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Provides proper session lifecycle management with automatic cleanup.
    Use this for all database operations in async contexts.
    
    Example:
        async for session in get_async_session():
            # Your database operations here
            await session.execute(...)
            await session.commit()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_async_db():
    """
    Initialize async database tables and schema.
    
    Creates the 'polymarket' schema and all required tables if they don't exist.
    Should be called once during application startup.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        async with async_engine.begin() as conn:
            # Create schema if it doesn't exist
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS polymarket;"))
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        print("Polymarket async database initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing async database: {e}")
        return False

class AsyncDatabaseUtils:
    """
    Utility class for async database operations with performance optimizations.
    
    Provides bulk insert methods and transaction management optimized
    for high-frequency WebSocket data ingestion.
    """
    
    @staticmethod
    async def bulk_insert_orderbooks(session: AsyncSession, orderbooks: list[dict]) -> bool:
        """
        Bulk insert orderbook records for optimal performance.
        
        Args:
            session: Active async database session
            orderbooks: List of orderbook dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            orderbook_objects = [OrderBook(**data) for data in orderbooks]
            session.add_all(orderbook_objects)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"Error bulk inserting orderbooks: {e}")
            return False
    
    @staticmethod
    async def bulk_insert_price_changes(session: AsyncSession, price_changes: list[dict]) -> bool:
        """
        Bulk insert price change records for optimal performance.
        
        Args:
            session: Active async database session
            price_changes: List of price change dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            price_objects = [PriceChange(**data) for data in price_changes]
            session.add_all(price_objects)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"Error bulk inserting price changes: {e}")
            return False
    
    @staticmethod
    async def bulk_insert_tick_changes(session: AsyncSession, tick_changes: list[dict]) -> bool:
        """
        Bulk insert tick size change records for optimal performance.
        
        Args:
            session: Active async database session
            tick_changes: List of tick change dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            tick_objects = [TickSizeChange(**data) for data in tick_changes]
            session.add_all(tick_objects)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"Error bulk inserting tick changes: {e}")
            return False

# For backwards compatibility and direct script execution
if __name__ == "__main__":
    """
    When run directly, initialize the async database.
    When imported, no automatic initialization occurs.
    """
    asyncio.run(init_async_db())