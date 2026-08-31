from pydantic import BaseModel, EmailStr, ConfigDict, Field
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from models.position import PositionSide, PositionStatus
from models.trade import TradeAction
from models.stock import LiquidityTier

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    cash_balance: Decimal

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class StockResponse(BaseModel):
    symbol: str
    name: str
    sector: Optional[str]
    current_price: Optional[Decimal]
    change_percent: Optional[Decimal]
    volume: Optional[int]
    liquidity_tier: LiquidityTier
    margin_requirement: Decimal
    max_leverage: Decimal
    shortable: bool

    model_config = ConfigDict(from_attributes=True)

class MarketStatusResponse(BaseModel):
    status: str
    next_open_at: Optional[str] = None

class PositionOpenRequest(BaseModel):
    symbol: str
    side: PositionSide
    leverage: Decimal
    quantity: int

class PositionCloseRequest(BaseModel):
    quantity_to_close: Decimal

class PositionResponse(BaseModel):
    id: UUID
    symbol: str
    side: PositionSide
    leverage: Decimal
    entry_price: Decimal
    quantity: Decimal
    margin_used: Decimal
    liquidation_price: Decimal
    status: PositionStatus
    opened_at: datetime
    current_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_percent: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)

class TradeResponse(BaseModel):
    id: UUID
    position_id: UUID
    symbol: str
    action: TradeAction
    leverage: Decimal
    price_executed: Decimal
    quantity: Decimal
    cash_delta: Decimal
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PortfolioHistorySnapshot(BaseModel):
    captured_at: datetime
    total_equity: Decimal

    model_config = ConfigDict(from_attributes=True)

class PortfolioResponse(BaseModel):
    cash_balance: Decimal
    positions_value: Decimal
    total_equity: Decimal
    history: List[PortfolioHistorySnapshot]

class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    total_equity: Decimal
