import os
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Boolean, DateTime, select
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./tradebot.db")

engine = create_async_engine(DB_URL, echo=True)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Position(Base):
    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    entry_price: Mapped[float] = mapped_column(Float)
    current_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="active") # active, moonbag_secured
    is_initial_investment_recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Predator Fields
    highest_price_seen: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trailing_stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

class TradeHistory(Base):
    __tablename__ = "trade_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String) # sell, buy
    profit_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String) # sell, buy
    status: Mapped[str] = mapped_column(String) # success, failed, split
    slippage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

if __name__ == "__main__":
    asyncio.run(init_db())
    print("Database initialized.")
