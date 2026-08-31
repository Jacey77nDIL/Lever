from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from decimal import Decimal
from models.position import Position, PositionStatus, PositionSide
from models.stock import Stock
from models.trade import Trade, TradeAction
from models.portfolio import OpenInterest
from services.trading_engine import compute_execution_price
from core.database import AsyncSessionLocal

async def run_margin_sweep():
    async with AsyncSessionLocal() as db:
        # Fetch all open positions joined with stocks
        stmt = select(Position, Stock).join(Stock, Position.symbol == Stock.symbol).where(Position.status == PositionStatus.OPEN)
        result = await db.execute(stmt)
        rows = result.all()

        for position, stock in rows:
            # Check liquidation conditions
            liquidate = False
            if position.side == PositionSide.LONG and stock.current_price <= position.liquidation_price:
                liquidate = True
            elif position.side == PositionSide.SHORT and stock.current_price >= position.liquidation_price:
                liquidate = True
            
            if liquidate:
                # Execute liquidation
                execution_price = compute_execution_price(stock.current_price, position.side, action_is_open=False, tier=stock.liquidity_tier)
                
                # Realize PnL
                if position.side == PositionSide.LONG:
                    realized_pnl = (execution_price - position.entry_price) * position.quantity
                else:
                    realized_pnl = (position.entry_price - execution_price) * position.quantity
                
                position.status = PositionStatus.LIQUIDATED
                position.exit_price = execution_price
                position.realized_pnl = realized_pnl
                
                # Cash delta returned to user = margin_used + realized_pnl
                cash_delta = position.margin_used + realized_pnl
                
                # Update user cash
                # Since we don't load user, let's just do a direct update
                await db.execute(
                    "UPDATE users SET cash_balance = cash_balance + :delta WHERE id = :uid",
                    {"delta": cash_delta, "uid": position.user_id}
                )
                
                # Create Trade log
                trade = Trade(
                    user_id=position.user_id,
                    position_id=position.id,
                    symbol=position.symbol,
                    action=TradeAction.LIQUIDATION,
                    leverage=position.leverage,
                    price_executed=execution_price,
                    quantity=position.quantity,
                    cash_delta=cash_delta
                )
                db.add(trade)
                
                # Update Open Interest
                if position.side == PositionSide.LONG:
                    await db.execute(
                        update(OpenInterest).where(OpenInterest.symbol == position.symbol)
                        .values(total_long_shares=OpenInterest.total_long_shares - position.quantity)
                    )
                else:
                    await db.execute(
                        update(OpenInterest).where(OpenInterest.symbol == position.symbol)
                        .values(total_short_shares=OpenInterest.total_short_shares - position.quantity)
                    )
                
        await db.commit()
