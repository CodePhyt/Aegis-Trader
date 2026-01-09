import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
from bot_brain import PredatorBot
from database import Position, TradeHistory, Base
from sqlalchemy import select
from loguru import logger

@pytest.mark.asyncio
async def test_predator_strategy():
    # Setup isolated DB
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    # Patch modules in bot_brain
    with patch("bot_brain.ExchangeClient") as MockExchange, \
         patch("core.executor.TradeExecutor.execute_smart_sell") as MockSmartSell:
        
        mock_client = MockExchange.return_value
        
        # 1. Setup Mock Config
        config = {
            "strategy": {
                "moonbag_target_multiplier": 2.0,
                "initial_sell_percentage": 0.5,
                "trailing_stop_percentage": 0.05,
                "volatility_guard_window_seconds": 0, # Disable delay for test speed
                "slippage_tolerance_pct": 0.005,
                "max_slippage_retry_chunks": 3
            },
            "system": {}
        }
        
        # 2. Init Bot
        # We need to inject config manually since bot_brain loads it global
        with patch("bot_brain.CONFIG", config):
            bot = PredatorBot()
            bot.exchange = mock_client
            # Re-init components with mock exchange if needed, but bot.executor already created.
            # However, execute_smart_sell is mocked.
            
            # 3. Setup Test DB
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            async with TestSessionLocal() as session:
                # Setup Position: ETH @ $2000
                pos = Position(
                    symbol="ETH",
                    entry_price=2000.0,
                    current_amount=10.0,
                    status="active"
                )
                session.add(pos)
                await session.commit()
                
                # TEST 1: MOONBAG TRIGGER
                # Price goes to $4000 (2x)
                # execute_smart_sell should be called with 50% (5.0 ETH)
                MockSmartSell.return_value = [{"id": "order_1"}] # success
                
                # First call: Detected as potential pump (Volatility Guard) - Should NOT sell yet
                await bot.strategist.analyze_position(session, pos, 4000.0)
                MockSmartSell.assert_not_called()
                
                # Second call: Confirmed pump - Should SELL
                await bot.strategist.analyze_position(session, pos, 4000.0)
                
                MockSmartSell.assert_called_with("ETH", 5.0)
                assert pos.status == "moonbag_secured"
                assert pos.current_amount == 5.0
                assert pos.trailing_stop_price == 4000.0 * (1 - 0.05) # 3800
                
                print("\n[PASS] MoonBag Secured triggered correctly.")
                
                # TEST 2: TRAILING STOP ADJUSTMENT
                # Price goes to $5000
                # Stop should move up to 5000 * 0.95 = 4750
                await bot.strategist.analyze_position(session, pos, 5000.0)
                assert pos.highest_price_seen == 5000.0
                assert pos.trailing_stop_price == 4750.0
                
                print(f"[PASS] Trailing Stop moved to {pos.trailing_stop_price}")
                
                # TEST 3: TRAILING STOP HIT
                # Price drops to $4700 (below 4750)
                # Should sell remaining 5.0
                MockSmartSell.reset_mock()
                MockSmartSell.return_value = [{"id": "order_2"}]
                
                await bot.strategist.analyze_position(session, pos, 4700.0)
                
                MockSmartSell.assert_called_with("ETH", 5.0)
                assert pos.status == "closed"
                assert pos.current_amount == 0
                
                print("[PASS] Trailing Stop triggered and position closed.")

    await test_engine.dispose()
