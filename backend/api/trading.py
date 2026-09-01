from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Any, List
from decimal import Decimal
import json

from core.database import get_db, get_redis
from core.config import settings
from api.deps import get_current_user
from models.user import User
from models.stock import Stock
from models.position import Position, PositionSide, PositionStatus
from models.trade import Trade, TradeAction
from models.portfolio import OpenInterest
from schemas import PositionOpenRequest, PositionCloseRequest, PositionResponse, TradeResponse
from services.trading_engine import compute_execution_price, compute_liquidation_price

router = APIRouter()

@router.post("/positions/open", response_model=PositionResponse)
async def open_position(
    req: PositionOpenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    # 1. Market must be open
    redis = await get_redis()
    market_status = await redis.get("market:status")
    if market_status != "open":
        raise HTTPException(status_code=403, detail="Market is closed")

    # Fetch stock
    stmt = select(Stock).where(Stock.symbol == req.symbol.upper())
    result = await db.execute(stmt)
    stock = result.scalars().first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 2. Validation
    if req.leverage > stock.max_leverage:
        raise HTTPException(status_code=400, detail=f"Leverage exceeds maximum allowed ({stock.max_leverage}x)")
    
    if req.side == PositionSide.SHORT and not stock.shortable:
        raise HTTPException(status_code=400, detail="Stock is not shortable")

    # Compute execution price
    execution_price = compute_execution_price(stock.current_price, req.side, action_is_open=True, tier=stock.liquidity_tier)
    
    # Compute notional & margin
    quantity = Decimal(req.quantity)
    notional = quantity * execution_price
    margin_used = notional / req.leverage

    if margin_used > current_user.cash_balance:
        raise HTTPException(status_code=400, detail="Insufficient cash balance")

    # 5. Open Interest & Concentration Checks (Simplified open interest check)
    stmt = select(OpenInterest).where(OpenInterest.symbol == stock.symbol)
    result = await db.execute(stmt)
    oi = result.scalars().first()
    if not oi:
        oi = OpenInterest(symbol=stock.symbol, total_long_shares=Decimal("0"), total_short_shares=Decimal("0"))
        db.add(oi)

    if stock.shares_outstanding and stock.shares_outstanding > 0:
        cap = Decimal(str(stock.shares_outstanding)) * settings.OPEN_INTEREST_CAP_PCT
        if req.side == PositionSide.LONG and (oi.total_long_shares + quantity) > cap:
            raise HTTPException(status_code=400, detail="open_interest_cap_reached")
        if req.side == PositionSide.SHORT and (oi.total_short_shares + quantity) > cap:
            raise HTTPException(status_code=400, detail="open_interest_cap_reached")

    # Update Open Interest
    if req.side == PositionSide.LONG:
        oi.total_long_shares += quantity
    else:
        oi.total_short_shares += quantity

    # 6. Execute Trade
    liquidation_price = compute_liquidation_price(
        entry_price=execution_price,
        side=req.side,
        initial_margin_fraction=stock.margin_requirement,
        leverage=req.leverage
    )

    current_user.cash_balance -= margin_used

    position = Position(
        user_id=current_user.id,
        symbol=stock.symbol,
        side=req.side,
        leverage=req.leverage,
        entry_price=execution_price,
        quantity=quantity,
        margin_used=margin_used,
        liquidation_price=liquidation_price
    )
    db.add(position)
    await db.flush() # flush to get position ID

    trade = Trade(
        user_id=current_user.id,
        position_id=position.id,
        symbol=stock.symbol,
        action=TradeAction.OPEN_LONG if req.side == PositionSide.LONG else TradeAction.OPEN_SHORT,
        leverage=req.leverage,
        price_executed=execution_price,
        quantity=quantity,
        cash_delta=-margin_used
    )
    db.add(trade)
    
    await db.commit()
    await db.refresh(position)
    return position

@router.post("/positions/{id}/close", response_model=PositionResponse)
async def close_position(
    id: str,
    req: PositionCloseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    # 1. Market must be open
    redis = await get_redis()
    market_status = await redis.get("market:status")
    if market_status != "open":
        raise HTTPException(status_code=403, detail="Market is closed")

    stmt = select(Position).where(Position.id == id, Position.user_id == current_user.id)
    result = await db.execute(stmt)
    position = result.scalars().first()
    if not position or position.status != PositionStatus.OPEN:
        raise HTTPException(status_code=404, detail="Open position not found")

    if req.quantity_to_close <= 0 or req.quantity_to_close > position.quantity:
        raise HTTPException(status_code=400, detail="Invalid quantity to close")

    # Fetch stock
    stmt = select(Stock).where(Stock.symbol == position.symbol)
    result = await db.execute(stmt)
    stock = result.scalars().first()

    execution_price = compute_execution_price(stock.current_price, position.side, action_is_open=False, tier=stock.liquidity_tier)
    
    # Calculate PnL for the closed portion
    if position.side == PositionSide.LONG:
        realized_pnl = (execution_price - position.entry_price) * req.quantity_to_close
    else:
        realized_pnl = (position.entry_price - execution_price) * req.quantity_to_close
    
    margin_returned = position.margin_used * (req.quantity_to_close / position.quantity)
    cash_returned = margin_returned + realized_pnl
    
    current_user.cash_balance += cash_returned

    trade = Trade(
        user_id=current_user.id,
        position_id=position.id,
        symbol=stock.symbol,
        action=TradeAction.CLOSE_LONG if position.side == PositionSide.LONG else TradeAction.CLOSE_SHORT,
        leverage=position.leverage,
        price_executed=execution_price,
        quantity=req.quantity_to_close,
        cash_delta=cash_returned
    )
    db.add(trade)

    # Update open interest
    stmt = select(OpenInterest).where(OpenInterest.symbol == stock.symbol)
    result = await db.execute(stmt)
    oi = result.scalars().first()
    if oi:
        if position.side == PositionSide.LONG:
            oi.total_long_shares -= req.quantity_to_close
        else:
            oi.total_short_shares -= req.quantity_to_close

    if req.quantity_to_close == position.quantity:
        position.status = PositionStatus.CLOSED
        position.margin_used = 0
        position.quantity = 0
        position.exit_price = execution_price
        position.realized_pnl = (position.realized_pnl or 0) + realized_pnl
    else:
        position.quantity -= req.quantity_to_close
        position.margin_used -= margin_returned
        position.realized_pnl = (position.realized_pnl or 0) + realized_pnl
        # Recompute liquidation price because margin fraction changed?
        # Actually liquidation price doesn't change on partial close since both quantity and margin scale down linearly.

    await db.commit()
    await db.refresh(position)
    return position

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    status: PositionStatus = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    stmt = select(Position, Stock).join(Stock, Position.symbol == Stock.symbol).where(Position.user_id == current_user.id)
    if status:
        stmt = stmt.where(Position.status == status)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    positions = []
    for pos, stock in rows:
        # We manually compute current unrealized PnL to include in the response
        unrealized_pnl = Decimal("0.0")
        if pos.status == PositionStatus.OPEN:
            if pos.side == PositionSide.LONG:
                unrealized_pnl = (stock.current_price - pos.entry_price) * pos.quantity
            else:
                unrealized_pnl = (pos.entry_price - stock.current_price) * pos.quantity
        
        setattr(pos, "current_price", stock.current_price)
        setattr(pos, "unrealized_pnl", unrealized_pnl)
        
        margin = pos.margin_used
        if margin > 0:
            setattr(pos, "unrealized_pnl_percent", (unrealized_pnl / margin) * 100)
        else:
            setattr(pos, "unrealized_pnl_percent", Decimal("0.0"))
            
        positions.append(pos)
        
    return positions

@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    stmt = select(Trade).where(Trade.user_id == current_user.id).order_by(Trade.executed_at.desc()).limit(50)
    result = await db.execute(stmt)
    return result.scalars().all()
