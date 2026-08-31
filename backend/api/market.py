from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, List
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_redis, get_db
from models.stock import Stock
from schemas import StockResponse, MarketStatusResponse

router = APIRouter()

@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status() -> Any:
    redis = await get_redis()
    status = await redis.get("market:status")
    
    # Optional logic to compute next_open_at could be added here
    return {"status": status or "closed", "next_open_at": None}

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
