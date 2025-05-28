"""
SQLAlchemy 2.0 + AsyncPG Models for Kalshi Data

This module provides async database models using SQLAlchemy 2.0 with asyncpg
for high-performance concurrent database operations. Essential for handling
real-time WebSocket data streams from Kalshi prediction markets.

Key Features:
- Async session management with connection pooling
- PostgreSQL-specific optimizations (JSONB, schemas)
- Proper transaction handling for high-frequency trading data
- Connection lifecycle management for WebSocket applications
- WE HAVE FULLY DEPRECATED NON ASYNC DBs - code will be deleted in future modules 
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator

# SQLAlchemy 2.0 imports
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from dotenv import load_dotenv

# Load environment variables from the root .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Get database configuration from environment variables
DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mypassword")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "mytradingdb")

# SQLAlchemy 2.0 declarative base
class Base(DeclarativeBase):
    """Base class for all database models using SQLAlchemy 2.0 syntax."""
    pass

class KalshiOrderbookSnapshot(Base):
    """Store Kalshi orderbook snapshots with full market depth."""
    __tablename__ = "kalshi_orderbook_snapshots"
    __table_args__ = {"schema": "kalshi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_ticker: Mapped[str] = mapped_column(String)
    sid: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[str] = mapped_column(String)
    yes_orders: Mapped[dict] = mapped_column(JSONB)
    no_orders: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

class KalshiOrderbookDelta(Base):
    """Store incremental orderbook changes for efficient processing."""
    __tablename__ = "kalshi_orderbook_deltas"
    __table_args__ = {"schema": "kalshi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_ticker: Mapped[str] = mapped_column(String)
    sid: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[str] = mapped_column(String)
    price_cents: Mapped[int] = mapped_column(Integer)
    delta: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

class KalshiOrderbookTrade(Base):
    """Store executed trades with pricing information."""
    __tablename__ = "kalshi_orderbook_trades"
    __table_args__ = {"schema": "kalshi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_ticker: Mapped[str] = mapped_column(String)
    sid: Mapped[int] = mapped_column(Integer)
    yes_price: Mapped[int] = mapped_column(Integer)
    no_price: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    taker_side: Mapped[str] = mapped_column(String)
    ts: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

class KalshiOrderbookFill(Base):
    """Store individual order fills for detailed trade analysis."""
    __tablename__ = "kalshi_orderbook_fills"
    __table_args__ = {"schema": "kalshi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String)
    order_id: Mapped[str] = mapped_column(String)
    market_ticker: Mapped[str] = mapped_column(String)
    sid: Mapped[int] = mapped_column(Integer)
    is_taker: Mapped[bool] = mapped_column(Boolean)
    side: Mapped[str] = mapped_column(String)
    yes_price: Mapped[int] = mapped_column(Integer)
    no_price: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String)
    ts: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

class KalshiOrderbookTickerV2(Base):
    """Store ticker updates with volume and open interest metrics."""
    __tablename__ = "kalshi_orderbook_ticker_v2"
    __table_args__ = {"schema": "kalshi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_ticker: Mapped[str] = mapped_column(String)
    sid: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    yes_bid: Mapped[int] = mapped_column(Integer)
    yes_ask: Mapped[int] = mapped_column(Integer)
    volume_delta: Mapped[int] = mapped_column(Integer)
    open_interest_delta: Mapped[int] = mapped_column(Integer)
    dollar_volume_delta: Mapped[int] = mapped_column(Integer)
    dollar_open_interest_delta: Mapped[int] = mapped_column(Integer)
    ts: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

# Async Database Setup with Connection Pooling
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine with optimized settings for WebSocket applications
async_engine = create_async_engine(
    DATABASE_URL,
    # Connection pool settings optimized for high-frequency trading data
    pool_size=20,          # Base number of connections
    max_overflow=30,       # Additional connections when needed
    pool_pre_ping=True,    # Validate connections before use
    pool_recycle=3600,     # Recycle connections every hour
    echo=False,            # Set to True for SQL debugging
    # AsyncPG specific optimizations
    connect_args={
        "server_settings": {
            "application_name": "kalshi_analytics",
            "jit": "off",  # Disable JIT for better performance with many short queries
        }
    }
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
    autoflush=True,          # Auto-flush before queries
    autocommit=False         # Manual transaction control
)

# Dependency for getting async database sessions
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get async database sessions.
    Automatically ensures database is initialized before providing session.
    
    Usage in WebSocket handlers:
        async with get_async_session() as session:
            # Database operations here
            await session.commit()
    """
    # Ensure database is initialized before providing session
    await ensure_async_db_initialized()
    
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
    Initialize database tables and schema asynchronously.
    Must be called with await in an async context.
    """
    try:
        async with async_engine.begin() as conn:
            # Create schema if it doesn't exist
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS kalshi"))
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        print("✅ Async database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing async database: {e}")
        return False

async def close_async_db():
    """Close all async database connections properly."""
    await async_engine.dispose()
    print("🔌 Async database connections closed")

'''
# Backwards compatibility - Sync database setup (deprecated)
# Keep this for gradual migration, but prefer async methods
def init_db():
    """
    DEPRECATED: Use init_async_db() instead.
    Synchronous database initialization for backwards compatibility.
    """
    print("⚠️  Warning: Using deprecated sync init_db(). Now, we are just forcefully calling init asyncdb.")
    
    import asyncio
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(init_async_db())
        loop.close()
        return result
    except Exception as e:
        print(f"Error in sync database initialization: {e}")
        return False
'''

# Database utility functions for common operations
class AsyncDatabaseUtils:
    """Utility class for common async database operations."""
    
    @staticmethod
    async def bulk_insert_snapshots(snapshots: list[dict], session: AsyncSession):
        """Efficiently insert multiple orderbook snapshots."""
        try:
            snapshot_objects = [
                KalshiOrderbookSnapshot(**snapshot) for snapshot in snapshots
            ]
            session.add_all(snapshot_objects)
            await session.commit()
            return len(snapshot_objects)
        except Exception as e:
            await session.rollback()
            raise e
    
    @staticmethod
    async def bulk_insert_trades(trades: list[dict], session: AsyncSession):
        """Efficiently insert multiple trade records."""
        try:
            trade_objects = [
                KalshiOrderbookTrade(**trade) for trade in trades
            ]
            session.add_all(trade_objects)
            await session.commit()
            return len(trade_objects)
        except Exception as e:
            await session.rollback()
            raise e
    
    @staticmethod
    async def get_latest_ticker(market_ticker: str, session: AsyncSession) -> Optional[KalshiOrderbookTickerV2]:
        """Get the most recent ticker for a market."""
        from sqlalchemy import select
        
        stmt = select(KalshiOrderbookTickerV2).where(
            KalshiOrderbookTickerV2.market_ticker == market_ticker
        ).order_by(KalshiOrderbookTickerV2.ts.desc()).limit(1)
        
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

# Module-level async initialization management
_db_initialized = False
_initialization_lock = asyncio.Lock()

async def ensure_async_db_initialized():
    """
    Ensure database is initialized exactly once using async methods.
    This is safe to call multiple times and from multiple coroutines.
    """
    global _db_initialized
    if _db_initialized:
        return True
    
    async with _initialization_lock:
        if _db_initialized:  # Double-check pattern
            return True
        
        success = await init_async_db()
        if success:
            _db_initialized = True
        return success

# For backwards compatibility - but now uses async under the hood
def init_db():
    """
    DEPRECATED: Use ensure_async_db_initialized() instead.
    Synchronous database initialization for backwards compatibility.
    """
    print("⚠️  Warning: Using deprecated sync init_db(). Switch to ensure_async_db_initialized() for better performance.")
    
    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
        # If we're in an async context, we can't run sync here
        print("🔄 Already in async context - database will be initialized on first async session use")
        return True
    except RuntimeError:
        # Not in async context, create one
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(ensure_async_db_initialized())
            loop.close()
            return result
        except Exception as e:
            print(f"Error in sync database initialization: {e}")
            return False

# Auto-initialize when imported, but safely handle async contexts
def _safe_module_init():
    """Safe module initialization that works in both sync and async contexts."""
    try:
        # Try to detect if we're in an async context
        loop = asyncio.get_running_loop()
        # If we're in an async context, defer initialization
        print("📦 Models module loaded in async context - call ensure_async_db_initialized() when ready")
    except RuntimeError:
        # Not in async context, safe to initialize
        print("📦 Models module loaded - initializing database...")
        init_db()

# Initialize on import if this is not the main module
if __name__ != "__main__":
    _safe_module_init()
else:
    # When run as main module, demonstrate async initialization
    async def main():
        print("🚀 Initializing Kalshi database with SQLAlchemy 2.0 + AsyncPG...")
        success = await ensure_async_db_initialized()
        if success:
            print("✅ Database initialization complete!")
        else:
            print("❌ Database initialization failed!")
        await close_async_db()
    
    asyncio.run(main())
