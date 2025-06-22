#!/usr/bin/env python3
"""
Check current database schema to see which fields are actually NOT NULL.
This helps us understand what needs to be migrated.
"""

import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mypassword")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "mytradingdb")

async def check_schema():
    """Check current schema for NOT NULL constraints."""
    
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )
    
    try:
        # Query to check NOT NULL constraints for Kalshi tables
        query = """
        SELECT 
            table_name, 
            column_name, 
            is_nullable, 
            data_type
        FROM information_schema.columns 
        WHERE table_schema = 'kalshi' 
        AND table_name LIKE 'kalshi_orderbook%'
        ORDER BY table_name, ordinal_position;
        """
        
        rows = await conn.fetch(query)
        
        print("📊 Current Kalshi Schema:")
        print("=" * 80)
        
        current_table = ""
        for row in rows:
            table, column, nullable, data_type = row
            
            if table != current_table:
                print(f"\n🔍 Table: {table}")
                current_table = table
            
            nullable_text = "NULL" if nullable == "YES" else "NOT NULL"
            status = "✅" if nullable == "YES" else "❌"
            print(f"  {status} {column:<25} {data_type:<15} {nullable_text}")
        
        # Check specifically for the problematic field
        print("\n🎯 Focus on ticker_v2 table:")
        ticker_rows = [r for r in rows if r[0] == 'kalshi_orderbook_ticker_v2']
        for row in ticker_rows:
            table, column, nullable, data_type = row
            if column in ['price', 'ts', 'received_at']:
                status = "✅ OK" if nullable == "YES" else "❌ NEEDS FIX"
                print(f"  {status} {column} is {'nullable' if nullable == 'YES' else 'NOT NULL'}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
