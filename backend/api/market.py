from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, List
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_redis, get_db
from models.stock import Stock
from schemas import StockResponse, MarketStatusResponse

router = APIRouter()

from datetime import datetime
from zoneinfo import ZoneInfo

@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status() -> Any:
    redis = await get_redis()
    status = await redis.get("market:status")
    is_closed = (status or "closed") == "closed"
    
    next_open_at = None
    if is_closed:
        now = datetime.now(ZoneInfo("Africa/Lagos"))
        weekday = now.weekday() # 0=Mon, ..., 4=Fri, 5=Sat, 6=Sun
        hour = now.hour
        
        if weekday < 5: # Mon-Fri
            if hour < 9:
                next_open_at = "opens today 9:00 AM WAT"
            elif hour >= 16:
                if weekday == 4: # Friday evening
                    next_open_at = "opens Monday 9:00 AM WAT"
                else:
                    next_open_at = "opens tomorrow 9:00 AM WAT"
            else:
                # Between 9 AM and 4 PM on a weekday, but market is closed! Must be a public holiday.
                if weekday == 4:
                    next_open_at = "opens Monday 9:00 AM WAT"
                else:
                    next_open_at = "opens tomorrow 9:00 AM WAT"
        else: # Weekend
            next_open_at = "opens Monday 9:00 AM WAT"
            
    return {"status": status or "closed", "next_open_at": next_open_at}

@router.get("/stocks", response_model=List[StockResponse])
async def get_stocks(search: str = Query(None), db: AsyncSession = Depends(get_db)) -> Any:
    if search:
        # If search is provided, we use the database to filter
        stmt = select(Stock).where((Stock.symbol.ilike(f"%{search}%")) | (Stock.name.ilike(f"%{search}%")))
        result = await db.execute(stmt)
        return result.scalars().all()
        
    # Otherwise, try to return from redis cache
    redis = await get_redis()
    cached = await redis.get("stocks:latest")
    
    if cached:
        data = json.loads(cached)
        # We need to map it to our StockResponse format, including liquidity_tier etc.
        # It's better to fetch from DB for full data including our derived fields
    
    stmt = select(Stock)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/stocks/{symbol}", response_model=StockResponse)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)) -> Any:
    stmt = select(Stock).where(Stock.symbol == symbol.upper())
    result = await db.execute(stmt)
    stock = result.scalars().first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock
