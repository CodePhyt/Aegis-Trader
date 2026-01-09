import asyncio
import signal
import sys
import json
from loguru import logger
from database import get_db_session, Position, init_db
from sqlalchemy import select
from core.exchange_client import ExchangeClient
from core.executor import TradeExecutor
from core.strategist import Strategist

# Load Config
# In a real app, use a proper config loader
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    logger.error("config.json not found! Using defaults.")
    CONFIG = {"strategy": {}, "system": {}}

class PredatorBot:
    def __init__(self):
        self.running = False
        self.exchange = ExchangeClient()
        self.executor = TradeExecutor(self.exchange, CONFIG)
        self.strategist = Strategist(self.executor, CONFIG)
        self.last_tick_time = {} # symbol -> time

    async def start(self):
        self.running = True
        logger.info("Predator Bot Starting...")
        
        # Init DB
        await init_db()
        
        # Determine Watchdog Timeout
        watchdog_timeout = CONFIG['system'].get('websocket_watchdog_timeout', 30)

        while self.running:
            try:
                async for session in get_db_session():
                    # 1. Sync Wallet & Positions
                    # In "Predator", we might sync less often than price checks
                    # But for now, we sync balances.
                    await self._sync_positions(session)
                    
                    # 2. Monitor Prices & Apply Strategy
                    # Iterate active positions
                    stmt = select(Position).where(Position.status.in_(["active", "moonbag_secured"]))
                    result = await session.execute(stmt)
                    positions = result.scalars().all()
                    
                    for pos in positions:
                        # Watchdog / Volatility tracking requires updates
                        pass

                    # BATCH OPTIMIZATION: Fetch all prices in one go
                    active_symbols = [p.symbol for p in positions]
                    if active_symbols:
                        prices = await self.exchange.fetch_tickers(active_symbols)
                        
                        for pos in positions:
                            if pos.symbol not in prices:
                                continue
                                
                            price = prices[pos.symbol]
                            
                            try:
                                # Apply Strategy
                                await self.strategist.analyze_position(session, pos, price)
                            except Exception as e:
                                logger.error(f"Strategy Error on {pos.symbol}: {e}")

                    await session.commit()
            
            except Exception as e:
                logger.error(f"Main Loop Error: {e}")
                # Reconnect logic if we suspect network down?
                # await self.exchange.reconnect()

            await asyncio.sleep(1)

    async def _sync_positions(self, db):
        # reuse sync logic or move to Executor? 
        # For now, quick impl to keep brain working
        try:
            balances = await self.exchange.fetch_balance()
            for symbol, amount in balances.items():
                stmt = select(Position).where(Position.symbol == symbol)
                result = await db.execute(stmt)
                pos = result.scalar_one_or_none()
                
                if not pos:
                     # New entry
                     price = await self.exchange.get_current_price(symbol) # could be blocking
                     # Calculate Fees (Predator Engine)
                     entry_price = await self.executor.calculate_breakeven_entry(symbol, price, 'buy')
                     
                     pos = Position(
                         symbol=symbol, 
                         current_amount=amount, 
                         entry_price=entry_price,
                         highest_price_seen=price,
                         status="active"
                     )
                     db.add(pos)
                     logger.info(f"New Position Tracked: {symbol} @ {entry_price} (Fee Adjusted)")
                else:
                    # Update amount?
                    # If amount changed externally, we might want to respect it
                    pass
        except Exception as e:
            logger.error(f"Sync Error: {e}")

    async def stop(self):
        logger.warning("Predator Shutdown Initiated...")
        self.running = False
        await self.exchange.close()
        logger.success("Shutdown Complete.")

# Global Bot Instance for Signals
bot = PredatorBot()

async def shutdown_handler(signal, loop):
    logger.warning(f"Received Exit Signal: {signal.name}")
    await bot.stop()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    logger.info("Cancelling pending tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Register Signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown_handler(s, loop)))

    try:
        loop.run_until_complete(bot.start())
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
