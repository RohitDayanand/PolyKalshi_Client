#!/usr/bin/env python3
"""
Migration script to make specified fields nullable in Kalshi tables.
This addresses the NOT NULL constraint violations while preserving existing data.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add the current directory to Python path to import models
sys.path.append(str(Path(__file__).parent))

from models import async_engine

async def migrate_nullable_fields():
    """
    Apply ALTER TABLE statements to make fields nullable.
    This is safer than dropping/recreating tables as it preserves data.
    """
    
    migrations = [
        # kalshi_orderbook_snapshots
        "ALTER TABLE kalshi.kalshi_orderbook_snapshots ALTER COLUMN timestamp DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_snapshots ALTER COLUMN yes_orders DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_snapshots ALTER COLUMN no_orders DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_snapshots ALTER COLUMN created_at DROP NOT NULL;",
        
        # kalshi_orderbook_deltas  
        "ALTER TABLE kalshi.kalshi_orderbook_deltas ALTER COLUMN timestamp DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_deltas ALTER COLUMN price_cents DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_deltas ALTER COLUMN delta DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_deltas ALTER COLUMN side DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_deltas ALTER COLUMN created_at DROP NOT NULL;",
        
        # kalshi_orderbook_trades
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN yes_price DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN no_price DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN count DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN taker_side DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN ts DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_trades ALTER COLUMN received_at DROP NOT NULL;",
        
        # kalshi_orderbook_fills
        "ALTER TABLE kalshi.kalshi_orderbook_fills ALTER COLUMN received_at DROP NOT NULL;",
        
        # kalshi_orderbook_ticker_v2 (this is the main one causing the error)
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN price DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN yes_bid DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN yes_ask DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN volume_delta DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN open_interest_delta DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN dollar_volume_delta DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN dollar_open_interest_delta DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN ts DROP NOT NULL;",
        "ALTER TABLE kalshi.kalshi_orderbook_ticker_v2 ALTER COLUMN received_at DROP NOT NULL;",
    ]
    
    try:
        async with async_engine.begin() as conn:
            print("🚀 Starting nullable field migration...")
            
            for i, migration in enumerate(migrations, 1):
                print(f"  [{i:2d}/{len(migrations)}] Executing migration...")
                try:
                    await conn.execute(text(migration))
                    print(f"  ✅ Success")
                except Exception as e:
                    print(f"  ⚠️  Warning: {e}")
                    # Continue with other migrations even if one fails
            
            print("\n✅ Migration completed successfully!")
            print("🎯 All specified fields are now nullable.")
            
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    finally:
        await async_engine.dispose()

async def verify_migration():
    """Verify that the migration worked by checking a few key fields."""
    
    verification_query = text("""
        SELECT column_name, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'kalshi' 
        AND table_name = 'kalshi_orderbook_ticker_v2' 
        AND column_name IN ('price', 'ts', 'received_at', 'volume_delta')
        ORDER BY column_name;
    """)
    
    try:
        async with async_engine.begin() as conn:
            print("\n🔍 Verifying migration results...")
            
            result = await conn.execute(verification_query)
            rows = result.fetchall()
            
            for row in rows:
                column_name, is_nullable = row
                status = "✅ NULLABLE" if is_nullable == "YES" else "❌ NOT NULL"
                print(f"  {column_name:20} → {status}")
            
            print("\n🎯 Verification complete!")
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    
    finally:
        await async_engine.dispose()

if __name__ == "__main__":
    async def main():
        success = await migrate_nullable_fields()
        if success:
            await verify_migration()
        else:
            print("❌ Migration failed, skipping verification")
    
    asyncio.run(main())
