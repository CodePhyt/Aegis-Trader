import ccxt.async_support as ccxt
import asyncio
import os
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class ExchangeClient:
    def __init__(self, exchange_id: str = 'binance'):
        self.exchange_id = exchange_id
        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.client = getattr(ccxt, exchange_id)({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot', 
            }
        })
        self.logger = logging.getLogger("ExchangeClient")

    async def fetch_tickers(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch multiple tickers at once if supported, or parallelize.
        Returns dict: symbol -> price
        """
        if not symbols:
            return {}
            
        try:
            # CCXT fetch_tickers support varies. 
            # If supported, it's 1 call. 
            # We assume most major exchanges support it.
            # Convert 'BTC' to 'BTC/USDT' roughly for crypto
            pairs = [f"{s}/USDT" if '/' not in s else s for s in symbols]
            
            # Check capabilities
            if self.client.has['fetchTickers']:
                tickers = await self.client.fetch_tickers(pairs)
                # Map back to simple symbol if needed or just return last price
                results = {}
                for pair, data in tickers.items():
                    # extract 'BTC' from 'BTC/USDT'
                    sym = pair.split('/')[0] if '/' in pair else pair
                    results[sym] = data['last']
                return results
            else:
                # Fallback to parallel fetch
                # Semaphore to avoid rate limits
                results = {}
                # TODO: Implement parallel fetch with semaphore
                # For now sequential fallback logic (simplified)
                for s in symbols:
                    results[s] = await self.get_current_price(s)
                return results

        except Exception as e:
            self.logger.error(f"Batch Tick Error: {e}")
            return {}

    async def get_exchange_id(self):
        return self.client.idclose()

    async def close(self):
        await self.client.close()

    async def fetch_balance(self) -> Dict[str, float]:
        """
        Fetch non-zero balances.
        Returns a dict of symbol -> amount (e.g., {'BTC': 0.5, 'ETH': 10.0})
        """
        try:
            balance = await self.client.fetch_balance()
            # Filter for non-zero free balances, exclude USDT/USD usually if not trading against it
            # But here we just want non-zero assets
            non_zero = {
                k: v['free'] 
                for k, v in balance.items() 
                if v['free'] > 0 and k not in ['USDT', 'USD', 'USDC'] # simplified exclusion
            }
            return non_zero
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            raise

    async def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol. Assumes USDT pair if no slash.
        """
        pair = f"{symbol}/USDT" if '/' not in symbol else symbol
        try:
            ticker = await self.client.fetch_ticker(pair)
            return ticker['last']
        except Exception as e:
            self.logger.error(f"Error fetching price for {pair}: {e}")
            # Fallback or re-raise? Re-raise for now.
            raise

    async def execute_sell_order(self, symbol: str, amount: float):
        """
        Market sell 50% (or specified amount).
        """
        pair = f"{symbol}/USDT"
        try:
            # Fetch market structure to check min notional if possible, but keeping simple for MVP
            self.logger.info(f"EXECUTING SELL: {symbol} amount={amount}")
            order = await self.client.create_market_sell_order(pair, amount)
            return order
        except Exception as e:
            self.logger.error(f"Failed to execute sell order for {symbol}: {e}")
            raise

    # Helper for simulation
    async def reconnect(self):
        """
        Force reconnect the exchange client.
        """
        self.logger.warning("Forcing Exchange Reconnection...")
        if self.client:
            await self.client.close()
        
        # Re-initialize
        self.client = getattr(ccxt, self.exchange_id)({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.logger.info("Exchange Client Reconnected.")

    async def watch_ticker_loop(self, symbol: str, callback):
        """
        Simulate WS stream or use actual watch_ticker if available.
        """
        # Note: This requires CCXT Pro for true WS. 
        # We will implement a robust polling loop here that acts as the "Stream"
        # and lets the Watchdog monitor it.
        while True:
            try:
                ticker = await self.client.fetch_ticker(symbol)
                await callback(symbol, ticker['last'])
                await asyncio.sleep(1) # simulate stream 1s
            except Exception as e:
                self.logger.error(f"Stream Error {symbol}: {e}")
                await asyncio.sleep(5)

