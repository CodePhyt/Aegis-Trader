"""
Core Execution Module for Aegis-Trader.

This module handles the physical execution of orders on the exchange.
It implements liquidity-aware logic (Iceberg/TWAP-lite) to minimize slippage
and calculates breakeven exit prices including fees.
"""
import asyncio
from loguru import logger
from typing import Dict, List, Optional
from core.exchange_client import ExchangeClient
# from database import TradeHistory # cyclic import risk? Executor usually writes to DB via Supervisor or direct.
# Let's keep Executor focused on Exchange interactions + logic.

class TradeExecutor:
    def __init__(self, exchange_client: ExchangeClient, config: dict):
        self.exchange = exchange_client
        strategy = config.get('strategy', {})
        try:
            self.slippage_tolerance = float(strategy.get('slippage_tolerance_pct', 0.005))
        except (TypeError, ValueError):
            self.slippage_tolerance = 0.005

        try:
            max_chunks = int(strategy.get('max_slippage_retry_chunks', 3))
        except (TypeError, ValueError):
            max_chunks = 3
        self.max_chunks = max(1, max_chunks)

    async def calculate_breakeven_entry(self, symbol: str, execution_price: float, side: str = 'buy') -> float:
        """
        Calculates the effective entry price including fees.
        """
        # For simplicity, getting default fee. In prod, fetch from exchange.
        # most exchanges ~0.1%
        fee_rate = 0.001 
        try:
            # Attempt to get actual markets if loaded
            markets = self.exchange.client.markets
            if markets:
                market = markets.get(symbol)
                if not market:
                    market = markets.get(self.exchange.normalize_symbol(symbol))
                if market:
                    taker = market.get('taker')
                    if taker is not None:
                        fee_rate = taker
        except Exception:
            pass

        if side == 'buy':
            return execution_price * (1 + fee_rate)
        else:
            return execution_price * (1 - fee_rate)

    async def get_liquidity_adjusted_price(self, symbol: str, amount: float, side: str) -> float:
        """
        Check order book. Return expected average price.
        """
        # Fetch top of book - usually enough for small retail.
        # For "Predator", we fetch depth.
        pair = self.exchange.normalize_symbol(symbol)
        ob = await self.exchange.client.fetch_order_book(pair, limit=20)
        orders = ob.get('bids') if side == 'sell' else ob.get('asks')
        orders = orders or []
        
        filled = 0.0
        weighted_sum = 0.0
        
        for price, quantity in orders:
            needed = amount - filled
            take = min(needed, quantity)
            weighted_sum += take * price
            filled += take
            if filled >= amount:
                break
        
        if filled == 0:
            return await self.exchange.get_current_price(symbol)
        if filled < amount:
            # Not enough liquidity in top 20; use average of available depth.
            return weighted_sum / filled
            
        return weighted_sum / amount

    async def execute_smart_sell(self, symbol: str, total_amount: float) -> List[Dict]:
        """
        Liquidity-aware sell. Splits order if slippage is too high.
        """
        if total_amount <= 0:
            logger.warning(f"Executor: Skipping sell for {symbol} amount={total_amount}")
            return []
        logger.info(f"Executor: Analyzing sell for {total_amount} {symbol}...")
        
        pair = self.exchange.normalize_symbol(symbol)
        ticker = await self.exchange.client.fetch_ticker(pair)
        last_price = ticker.get('last')
        if not last_price or last_price <= 0:
            last_price = await self.exchange.get_current_price(symbol)
        if not last_price or last_price <= 0:
            logger.warning(f"Executor: Missing last price for {symbol}, executing without slippage check.")
            order = await self.exchange.execute_sell_order(symbol, total_amount)
            return [order]
        
        # Check impact
        avg_price = await self.get_liquidity_adjusted_price(symbol, total_amount, 'sell')
        if not avg_price or avg_price <= 0:
            logger.warning(f"Executor: Missing liquidity price for {symbol}, executing without slippage check.")
            order = await self.exchange.execute_sell_order(symbol, total_amount)
            return [order]
        slippage = max(0.0, (last_price - avg_price) / last_price)
        
        logger.info(f"Executor: Est. Slippage for {symbol}: {slippage:.4%}")
        
        executions = []
        
        if slippage > self.slippage_tolerance:
            logger.warning(f"Slippage > {self.slippage_tolerance:.1%}. Splitting order (TWAP-lite).")
            chunk_size = total_amount / self.max_chunks
            
            for i in range(self.max_chunks):
                logger.info(f"Executing Chunk {i+1}/{self.max_chunks}...")
                order = await self.exchange.execute_sell_order(symbol, chunk_size)
                executions.append(order)
                # Wait a bit between chunks? logic says TWAP-lite.
                await asyncio.sleep(2) 
        else:
            order = await self.exchange.execute_sell_order(symbol, total_amount)
            executions.append(order)
            
        return executions
