from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any, List
import json

from core.database import get_db, get_redis
from api.deps import get_current_user
from models.user import User
from models.portfolio import PortfolioSnapshot
from schemas import PortfolioResponse, PortfolioHistorySnapshot, LeaderboardEntry

router = APIRouter()

@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    stmt = select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == current_user.id).order_by(PortfolioSnapshot.captured_at.asc())
    result = await db.execute(stmt)
    history = result.scalars().all()
    
    # Generate response
    # We should compute the real-time value here if needed, but for the history we use snapshots
    # To get current real-time value, we'd need to fetch positions. For now, use the last snapshot or current cash if none.
    
    if history:
        last_snap = history[-1]
        cash_balance = last_snap.cash_balance
        positions_value = last_snap.positions_value
        total_equity = last_snap.total_equity
    else:
        cash_balance = current_user.cash_balance
        positions_value = 0.0
        total_equity = current_user.cash_balance
        
    history_data = [
        PortfolioHistorySnapshot(captured_at=h.captured_at, total_equity=h.total_equity) for h in history
    ]
        
    return PortfolioResponse(
        cash_balance=cash_balance,
        positions_value=positions_value,
        total_equity=total_equity,
        history=history_data
    )

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    window: str = Query("all"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Note: Weekly window not fully implemented yet, defaulting to 'all' using the latest snapshot cache
    redis = await get_redis()
    cached = await redis.get("leaderboard:top")
    
    if cached:
        return json.loads(cached)
        
    return []
