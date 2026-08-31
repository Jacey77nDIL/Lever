import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import text
from decimal import Decimal
from models.user import User
from models.position import Position, PositionStatus, PositionSide
from models.stock import Stock
from models.portfolio import PortfolioSnapshot
from core.database import AsyncSessionLocal, get_redis

async def run_portfolio_snapshot():
    async with AsyncSessionLocal() as db:
        # We need to compute total equity for every user.
        # total_equity = cash_balance + sum(unrealized_pnl + margin_used) for all OPEN positions
        
        # Load all users and their open positions
        stmt = select(User)
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        stmt = select(Position, Stock).join(Stock, Position.symbol == Stock.symbol).where(Position.status == PositionStatus.OPEN)
        result = await db.execute(stmt)
        rows = result.all()
        
        # Group positions by user
        user_positions = {}
        for pos, stock in rows:
            if pos.user_id not in user_positions:
                user_positions[pos.user_id] = []
            user_positions[pos.user_id].append((pos, stock))
            
        leaderboard_data = []
            
        for user in users:
            positions = user_positions.get(user.id, [])
            positions_value = Decimal("0.0")
            
            for pos, stock in positions:
                current_price = stock.current_price
                if pos.side == PositionSide.LONG:
                    unrealized_pnl = (current_price - pos.entry_price) * pos.quantity
                else:
                    unrealized_pnl = (pos.entry_price - current_price) * pos.quantity
                
                positions_value += pos.margin_used + unrealized_pnl
                
            total_equity = user.cash_balance + positions_value
            
            snapshot = PortfolioSnapshot(
                user_id=user.id,
                cash_balance=user.cash_balance,
                positions_value=positions_value,
                total_equity=total_equity
            )
            db.add(snapshot)
            
            leaderboard_data.append({
                "username": user.username,
                "total_equity": float(total_equity)
            })
            
        await db.commit()
        
        # Sort leaderboard and save to Redis
        leaderboard_data.sort(key=lambda x: x["total_equity"], reverse=True)
        # Assign ranks
        for i, item in enumerate(leaderboard_data):
            item["rank"] = i + 1
            
        redis = await get_redis()
        await redis.set("leaderboard:top", json.dumps(leaderboard_data), ex=3600)
