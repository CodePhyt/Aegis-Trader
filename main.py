from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db_session, Position, TradeHistory
import os

app = FastAPI(title="MoonBag Auto Trader API")

# Pydantic Models for Response
class PositionRead(BaseModel):
    symbol: str
    entry_price: float
    current_amount: float
    status: str
    is_initial_investment_recovered: bool
    highest_price_seen: Optional[float]
    trailing_stop_price: Optional[float]
    last_updated: Optional[datetime]

class TradeRead(BaseModel):
    id: int
    symbol: str
    amount: float
    price: float
    type: str
    timestamp: datetime

class SettingsUpdate(BaseModel):
    check_interval: int

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow()}

@app.get("/portfolio", response_model=List[PositionRead])
async def get_portfolio(db: AsyncSession = Depends(get_db_session)):
    stmt = select(Position)
    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/history", response_model=List[TradeRead])
async def get_history(limit: int = 50, db: AsyncSession = Depends(get_db_session)):
    stmt = select(TradeHistory).order_by(desc(TradeHistory.timestamp)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@app.post("/settings")
async def update_settings(settings: SettingsUpdate):
    # In a real app, we might write this to .env or a DB settings table.
    # For now, we'll just log it and say we rely on restart.
    return {"message": f"Settings received. Please restart bot to apply interval: {settings.check_interval}"}

@app.post("/sync")
async def trigger_sync(db: AsyncSession = Depends(get_db_session)):
    """
    Trigger a manual wallet sync.
    In a real app, this might signal the background bot via channel/redis.
    For MVP with shared DB, we can just let the bot do it next tick, 
    or expose a method if running in same process (but we are not, likely).
    
    Actually, since bot_brain.py runs separately, this endpoint 
    just acknowledges the request. 
    To truly sync immediately, we'd need IPC.
    For this MVP, we'll assume the user just wants to know the bot is alive 
    or we can force a DB update if this process had access to exchange keys.
    
    Let's implement a simple "Check Status" for now or just return ok.
    """
    return {"status": "Sync request received (Bot scans every 60s)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
