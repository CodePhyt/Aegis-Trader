import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from bot_brain import MoonBagBot
from database import Position, TradeHistory, init_db, get_db_session, engine, Base
from sqlalchemy import select

# Use an in-memory SQLite DB for testing
# We need to override the engine in database.py or just use the one there 
# if we configured it to be flexible.
# Ideally we patch the DB_URL or engine, but for simplicity let's rely on 
# the fact that database.py uses a file. 
# For *simulation*, we want to test the logic.

@pytest.mark.asyncio
async def test_moonbag_strategy_simulation():
    # Setup isolated test DB
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    # 1. Setup Mock Exchange
    with patch("bot_brain.ExchangeClient") as MockExchange:
        mock_client = MockExchange.return_value
        
        # Scenario: User has 1.0 BTC bought at $10,000 (implicitly via first sync)
        mock_client.fetch_balance = AsyncMock(return_value={"BTC": 1.0})
        
        # Initial price: $10,000
        mock_client.get_current_price = AsyncMock(return_value=10000.0)
        mock_client.execute_sell_order = AsyncMock(return_value={"id": "order_123"})
        
        # 2. Init Bot
        bot = MoonBagBot()
        # Inject the mock just in case init created a real one (though we patched class)
        bot.exchange = mock_client 
        
        # 3. Setup Test DB Structure
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        async with TestSessionLocal() as session:
            # 4. Phase 1: Initial Sync (Entry)
            await bot.sync_wallet(session)
            
            # Verify Position Created
            stmt = select(Position).where(Position.symbol == "BTC")
            result = await session.execute(stmt)
            pos = result.scalar_one()
            assert pos.entry_price == 10000.0
            assert pos.current_amount == 1.0
            assert pos.status == "active"
            
            # 5. Phase 2: Price Pump (2x)
            mock_client.get_current_price.return_value = 20000.0 # MOON!
            
            # 6. Run Strategy Check
            await bot.check_strategy(session)
            
            # 7. Assertions
            # Should have sold 50% = 0.5 BTC
            mock_client.execute_sell_order.assert_called_once_with("BTC", 0.5)
            
            # Verify DB State
            await session.refresh(pos)
            assert pos.status == "moonbag_secured"
            assert pos.is_initial_investment_recovered is True
            assert pos.current_amount == 0.5 
            
            # Verify History
            stmt_hist = select(TradeHistory).where(TradeHistory.symbol == "BTC")
            result_hist = await session.execute(stmt_hist)
            trades = result_hist.scalars().all()
            assert len(trades) == 1
            assert trades[0].amount == 0.5
            assert trades[0].price == 20000.0
            assert trades[0].type == "sell"

            print("\nSimulation PASSED: BTC Pumped 100%, Bot Sold 50%!")

    await test_engine.dispose()
