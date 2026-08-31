import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update

from core.database import AsyncSessionLocal
from models.stock import Stock, StockPriceSnapshot, LiquidityTier

async def run_monthly_tier_classification():
    async with AsyncSessionLocal() as db:
        # 1st of month logic
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        stmt = select(Stock)
        result = await db.execute(stmt)
        stocks = result.scalars().all()
        
        for stock in stocks:
            # fetch snapshots from last 30 days
            snap_stmt = select(StockPriceSnapshot).where(
                StockPriceSnapshot.symbol == stock.symbol,
                StockPriceSnapshot.captured_at >= thirty_days_ago
            ).order_by(StockPriceSnapshot.captured_at.asc())
            
            snap_result = await db.execute(snap_stmt)
            snapshots = snap_result.scalars().all()
            
            if not snapshots:
                continue
                
            # Compute data_days
            days_set = set(snap.captured_at.date() for snap in snapshots)
            data_days = len(days_set)
            
            if data_days < 5:
                # Insufficient historical data to compute a new tier.
                # Keep the existing tier to avoid downgrading everything to RESTRICTED.
                continue
            
            # Compute market_cap
            # using latest snapshot or current_price
            market_cap = stock.current_price * Decimal(stock.shares_outstanding or 0)
            
            # Compute avg_daily_value_traded
            # for each day, max volume snapshot * close price
            daily_volumes = {}
            daily_prices = {}
            for snap in snapshots:
                date = snap.captured_at.date()
                vol = snap.volume or 0
                if date not in daily_volumes or vol > daily_volumes[date]:
                    daily_volumes[date] = vol
                    daily_prices[date] = snap.price
                    
            if daily_volumes:
                total_value = sum(daily_volumes[d] * daily_prices[d] for d in daily_volumes)
                avg_daily_value_traded = total_value / len(daily_volumes)
            else:
                avg_daily_value_traded = Decimal("0")
                
            # Compute volatility (std dev of daily change_percent)
            # Not fully strict std dev but a simple approximation or standard math
            changes = [snap.change_percent or Decimal("0") for snap in snapshots]
            if len(changes) > 1:
                mean_change = sum(changes) / len(changes)
                variance = sum((c - mean_change) ** 2 for c in changes) / (len(changes) - 1)
                volatility = variance.sqrt() if hasattr(variance, "sqrt") else Decimal(str(float(variance)**0.5))
            else:
                volatility = Decimal("0")
                
            # Evaluate tier
            tier = LiquidityTier.RESTRICTED
            margin_req = Decimal("1.0")
            max_lev = Decimal("1.0")
            shortable = False
            
            if data_days >= 5 and market_cap >= Decimal("500000000000") and avg_daily_value_traded >= Decimal("100000000") and volatility < Decimal("0.03"):
                tier = LiquidityTier.BLUE_CHIP
                margin_req = Decimal("0.25")
                max_lev = Decimal("4.0")
                shortable = True
            elif data_days >= 5 and market_cap >= Decimal("50000000000") and avg_daily_value_traded >= Decimal("20000000"):
                tier = LiquidityTier.ESTABLISHED
                margin_req = Decimal("0.40")
                max_lev = Decimal("2.5")
                shortable = True
            elif data_days >= 5 and len([v for v in daily_volumes.values() if v > 0]) > (data_days / 2):
                tier = LiquidityTier.VOLATILE
                margin_req = Decimal("0.75")
                max_lev = Decimal("1.33")
                shortable = True
                
            stock.liquidity_tier = tier
            stock.margin_requirement = margin_req
            stock.max_leverage = max_lev
            stock.shortable = shortable
            stock.tier_last_computed_at = now
            
        await db.commit()
