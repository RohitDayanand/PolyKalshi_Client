import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import sys
import os
from models import (
    get_async_session,
    KalshiOrderbookSnapshot,
    KalshiOrderbookDelta,
    KalshiOrderbookTrade,
    KalshiOrderbookFill,
    KalshiOrderbookTickerV2,
    ensure_async_db_initialized
)

class OrderbookProcessor:
    def __init__(self):
        self.current_snapshot = None
        self.last_sequence = {}  # Track last sequence number for each sid

    async def process_snapshot(self, message: Dict) -> None:
        try:
            sid = message.get('sid')
            seq = message.get('seq')
            msg_data = message.get('msg', {})
            market_ticker = msg_data.get('market_ticker')
            timestamp = datetime.now().isoformat()
            yes_orders = msg_data.get('yes', [])
            no_orders = msg_data.get('no', [])
            
            async with get_async_session() as session:
                snapshot = KalshiOrderbookSnapshot(
                    market_ticker=market_ticker,
                    sid=sid,
                    seq=seq,
                    timestamp=timestamp,
                    yes_orders=yes_orders,
                    no_orders=no_orders
                )
                session.add(snapshot)
                await session.commit()
                
            self.current_snapshot = {
                'market_ticker': market_ticker,
                'sid': sid,
                'seq': seq,
                'yes': msg_data.get('yes', []),
                'no': msg_data.get('no', [])            }
        except Exception as e:
            print(f"Error processing snapshot: {e}")

    async def process_delta(self, message: Dict) -> None:
        try:
            sid = message.get('sid')
            seq = message.get('seq')
            msg_data = message.get('msg', {})
            market_ticker = msg_data.get('market_ticker')
            timestamp = datetime.now().isoformat()
            
            async with get_async_session() as session:
                delta = KalshiOrderbookDelta(
                    market_ticker=market_ticker,
                    sid=sid,
                    seq=seq,
                    timestamp=timestamp,
                    price_cents=msg_data.get('price'),
                    delta=msg_data.get('delta'),
                    side=msg_data.get('side')
                )
                session.add(delta)
                await session.commit()
                
            if self.current_snapshot and self.current_snapshot['market_ticker'] == market_ticker:
                self._update_snapshot_with_delta(msg_data)
        except Exception as e:
            print(f"Error processing delta: {e}")

    def _update_snapshot_with_delta(self, delta_data: Dict) -> None:
        if not self.current_snapshot:
            return
        side = delta_data.get('side')
        price = delta_data.get('price')
        delta = delta_data.get('delta')
        orders = self.current_snapshot[side]
        found = False
        for i, order in enumerate(orders):
            if order[0] == price:
                new_size = order[1] + delta
                if new_size <= 0:
                    orders.pop(i)
                else:
                    orders[i][1] = new_size
                found = True
                break
        if not found and delta > 0:
            orders.append([price, delta])
        orders.sort(key=lambda x: x[0], reverse=(side == 'yes'))

    async def process_trade(self, message: Dict) -> None:
        try:
            sid = message.get('sid')
            msg_data = message.get('msg', {})
            market_ticker = msg_data.get('market_ticker')
            yes_price = msg_data.get('yes_price')
            no_price = msg_data.get('no_price')
            count = msg_data.get('count')
            taker_side = msg_data.get('taker_side')
            ts = msg_data.get('ts')
            
            async with get_async_session() as session:
                trade = KalshiOrderbookTrade(
                    market_ticker=market_ticker,
                    sid=sid,
                    yes_price=yes_price,
                    no_price=no_price,
                    count=count,
                    taker_side=taker_side,
                    ts=ts
                )                
                session.add(trade)
                await session.commit()
        except Exception as e:
            print(f"Error processing trade: {e}")

    async def process_fill(self, message: Dict) -> None:
        try:
            sid = message.get('sid')
            msg_data = message.get('msg', {})
            trade_id = msg_data.get('trade_id')
            order_id = msg_data.get('order_id')
            market_ticker = msg_data.get('market_ticker')
            is_taker = msg_data.get('is_taker')
            side = msg_data.get('side')
            yes_price = msg_data.get('yes_price')
            no_price = msg_data.get('no_price')
            count = msg_data.get('count')
            action = msg_data.get('action')
            ts = msg_data.get('ts')
            
            async with get_async_session() as session:
                fill = KalshiOrderbookFill(
                    trade_id=trade_id,
                    order_id=order_id,
                    market_ticker=market_ticker,
                    sid=sid,
                    is_taker=is_taker,
                    side=side,
                    yes_price=yes_price,
                    no_price=no_price,
                    count=count,
                    action=action,
                    ts=ts
                )
                session.add(fill)
                await session.commit()        
        except Exception as e:
            print(f"Error processing fill: {e}")

    async def process_ticker_v2(self, message: Dict) -> None:
        try:
            sid = message.get('sid')
            msg_data = message.get('msg', {})
            market_ticker = msg_data.get('market_ticker')
            price = msg_data.get('price', None)
            yes_bid = msg_data.get('yes_bid', None)
            yes_ask = msg_data.get('yes_ask', None)
            volume_delta = msg_data.get('volume_delta', None)
            open_interest_delta = msg_data.get('open_interest_delta', None)
            dollar_volume_delta = msg_data.get('dollar_volume_delta', None)
            dollar_open_interest_delta = msg_data.get('dollar_open_interest_delta', None)
            ts = msg_data.get('ts', None)
            
            async with get_async_session() as session:
                ticker = KalshiOrderbookTickerV2(
                    market_ticker=market_ticker,
                    sid=sid,
                    price=price,
                    yes_bid=yes_bid,
                    yes_ask=yes_ask,
                    volume_delta=volume_delta,
                    open_interest_delta=open_interest_delta,
                    dollar_volume_delta=dollar_volume_delta,
                    dollar_open_interest_delta=dollar_open_interest_delta,
                    ts=ts
                )
                session.add(ticker)
                await session.commit()
        except Exception as e:
            print(f"Error processing ticker_v2: {e}")