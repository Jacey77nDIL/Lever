import asyncio
import httpx
import json
from decimal import Decimal
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert

from core.config import settings
from core.database import AsyncSessionLocal, get_redis
from models.stock import Stock, StockPriceSnapshot, LiquidityTier
from services.margin_sweep import run_margin_sweep
from services.portfolio_snapshot import run_portfolio_snapshot
from services.liquidity_tiers import run_monthly_tier_classification

scheduler = AsyncIOScheduler()

async def check_market_status():
    """Run once a day at 9:00 AM to check if market is open (not a holiday)."""
    headers = {"X-API-Key": settings.KOBO_API_KEY}
    url = f"{settings.KOBO_API_BASE_URL}/api/ngxdata/market-status"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            status_data = data.get("data", {}) if isinstance(data, dict) else {}
            raw_status = status_data.get("status") or data.get("status", "closed")
            is_open = status_data.get("is_open", False) or str(raw_status).lower() == "open"
            status = "open" if is_open else "closed"
        except Exception as e:
            # Fallback on failure
            status = "closed"
            
    redis = await get_redis()
    await redis.set("market:status", status)

async def pull_stock_prices(force: bool = False):
    """Run hourly from 9 to 4 if market is open, or force run on initial sync."""
    redis = await get_redis()
    market_status = await redis.get("market:status")
    
    # If market is closed and not forced, do not pull prices
    if market_status != "open" and not force:
        return
        
    headers = {"X-API-Key": settings.KOBO_API_KEY}
    url = f"{settings.KOBO_API_BASE_URL}/api/ngxdata/stocks"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return

    if isinstance(data, dict):
        stocks_list = data.get("stocks", [])
    elif isinstance(data, list):
        stocks_list = data
    else:
        return

    if not stocks_list:
        return

    # Update Postgres & Redis
    async with AsyncSessionLocal() as db:
        # Prepare bulk dictionaries
        stock_dicts = []
        snap_dicts = []
        for stock_data in stocks_list:
            symbol = stock_data.get("symbol")
            if not symbol:
                continue
            
            stock_dicts.append({
                "symbol": symbol,
                "name": stock_data.get("name", ""),
                "sector": stock_data.get("sector"),
                "shares_outstanding": stock_data.get("shares_outstanding"),
                "current_price": stock_data.get("current_price"),
                "change_percent": stock_data.get("change_percent"),
                "volume": stock_data.get("volume"),
                "pe_ratio": stock_data.get("pe_ratio"),
            })
            
            snap_dicts.append({
                "symbol": symbol,
                "price": stock_data.get("current_price"),
                "change_percent": stock_data.get("change_percent"),
                "volume": stock_data.get("volume"),
            })
            
            # Redis individual stock cache
            await redis.set(f"stock:{symbol}", json.dumps(stock_data), ex=3600)
            
        if stock_dicts:
            # Bulk Upsert Stocks
            stmt = insert(Stock)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol"],
                set_=dict(
                    name=stmt.excluded.name,
                    sector=stmt.excluded.sector,
                    shares_outstanding=stmt.excluded.shares_outstanding,
                    current_price=stmt.excluded.current_price,
                    change_percent=stmt.excluded.change_percent,
                    volume=stmt.excluded.volume,
                    pe_ratio=stmt.excluded.pe_ratio,
                )
            )
            await db.execute(stmt, stock_dicts)
            
            # Bulk Insert Snapshots
            snap_stmt = insert(StockPriceSnapshot)
            await db.execute(snap_stmt, snap_dicts)
            
        await db.commit()
    
    # Redis all stocks cache
    await redis.set("stocks:latest", json.dumps(stocks_list), ex=3600)
    
    # Run dependent jobs
    await run_margin_sweep()
    await run_portfolio_snapshot()

async def initial_sync():
    await check_market_status()
    await pull_stock_prices(force=True)

def start_scheduler():
    # Run market status check at 09:00 Mon-Fri WAT (Africa/Lagos)
    scheduler.add_job(
        check_market_status,
        CronTrigger(day_of_week='mon-fri', hour=9, minute=0, timezone='Africa/Lagos')
    )
    
    # Run price pull every hour from 09:00 to 16:00 Mon-Fri WAT
    scheduler.add_job(
        pull_stock_prices,
        CronTrigger(day_of_week='mon-fri', hour='9-16', minute=0, timezone='Africa/Lagos')
    )
    
    # Run monthly tier classification on the 1st of each month at 00:00 WAT
    scheduler.add_job(
        run_monthly_tier_classification,
        CronTrigger(day=1, hour=0, minute=0, timezone='Africa/Lagos')
    )
    
    scheduler.start()
    asyncio.create_task(initial_sync())
