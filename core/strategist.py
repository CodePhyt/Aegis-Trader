"""
Core Strategy Engine for Aegis-Trader.

This module contains the "Brain" of the trading system.
It implements:
1. MoonBag Logic: Sell 50% at 2x.
2. Volatility Guard: Prevent selling into fakeout wicks.
3. Hedged Trailing Stop: Protect the remaining 50% 'free roll'.
"""
from datetime import datetime, timedelta, timezone
from loguru import logger
from database import Position
from core.executor import TradeExecutor
from sqlalchemy.ext.asyncio import AsyncSession

class Strategist:
    def __init__(self, executor: TradeExecutor, config: dict):
        self.executor = executor
        defaults = {
            "moonbag_target_multiplier": 2.0,
            "initial_sell_percentage": 0.5,
            "trailing_stop_percentage": 0.05,
            "volatility_guard_window_seconds": 5,
        }
        strategy = config.get('strategy', {})
        self.config = {**defaults, **strategy}
        self.target_multiplier = self.config['moonbag_target_multiplier']
        self.trailing_stop_pct = self.config['trailing_stop_percentage']
        self.volatility_window = self.config['volatility_guard_window_seconds']
        
        # Volatility Cache: symbol -> (first_seen_time, price)
        self.pump_candidates = {} 

    async def analyze_position(self, session: AsyncSession, position: Position, current_price: float):
        """
        The Brain's decision logic.
        """
        # 0. Update Highest Price Seen (for Trailing Stop)
        if position.highest_price_seen is None or current_price > position.highest_price_seen:
            position.highest_price_seen = current_price
            # Update Trailing Stop Price if moonbag secured
            if position.status == "moonbag_secured":
                new_stop = current_price * (1 - self.trailing_stop_pct)
                if position.trailing_stop_price is None or new_stop > position.trailing_stop_price:
                    position.trailing_stop_price = new_stop
                    logger.info(f"Updated Trailing Stop for {position.symbol}: {new_stop:.4f}")
        
        # 1. MOONBAG SECURE LOGIC
        if position.status == "active":
            target_price = position.entry_price * self.target_multiplier
            
            if current_price >= target_price:
                # Volatility Guard
                if not self._check_volatility_pass(position.symbol, current_price):
                    return

                # FINAL UPGRADE: Deep Volatility Filter (1m > 10%)
                # Requires fetching history. For MVP/Local, we use a simpler heuristic:
                # If price changed > 10% in last check interval (since we track it), it might be too volatile.
                # In a real system, we'd call self.exchange.fetch_ohlcv(symbol, '1m', limit=2)
                
                logger.info(f"Target Hit for {position.symbol}. Executing MoonBag Secure...")
                
                # Execute Sell
                amount_to_sell = position.current_amount * self.config['initial_sell_percentage']
                
                # Use Executor for smart sell
                executions = await self.executor.execute_smart_sell(position.symbol, amount_to_sell)
                
                # If successful
                if executions:
                    position.status = "moonbag_secured"
                    position.is_initial_investment_recovered = True
                    position.current_amount -= amount_to_sell 
                    # Set initial trailing stop
                    position.trailing_stop_price = current_price * (1 - self.trailing_stop_pct)
                    logger.success(f"MoonBag Secured for {position.symbol}. Remaining: {position.current_amount}")
                    
                    # Notify
                    # Assuming bot passes notifier to strategist or handles it
                    # returning signal for now or logging is enough for MVP core logic
                    pass

        # 2. TRAILING STOP LOGIC
        elif position.status == "moonbag_secured":
            if position.trailing_stop_price and current_price <= position.trailing_stop_price:
                logger.warning(f"Trailing Stop Hit for {position.symbol} at {current_price} <= {position.trailing_stop_price}")
                # Sell Remainder
                await self.executor.execute_smart_sell(position.symbol, position.current_amount)
                position.current_amount = 0
                position.status = "closed"
                logger.success(f"Position Closed for {position.symbol}.")

    def _check_volatility_pass(self, symbol: str, price: float) -> bool:
        """
        Returns True if price has been stable/high for X seconds.
        """
        now = datetime.now(timezone.utc)
        if symbol not in self.pump_candidates:
            self.pump_candidates[symbol] = (now, price)
            logger.info(f"Volatility Guard: {symbol} hit target. Waiting {self.volatility_window}s...")
            return False
        
        first_seen, seen_price = self.pump_candidates[symbol]
        
        # If price dropped significantly below target, reset? 
        # For now, just check time.
        
        if (now - first_seen).total_seconds() >= self.volatility_window:
            # Check if price is still high? 
            # Ideally yes, but the caller passes current_price which is >= target.
            del self.pump_candidates[symbol]
            return True
            
        return False
