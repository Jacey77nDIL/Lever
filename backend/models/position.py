import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"

class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    symbol = Column(String(20), ForeignKey("stocks.symbol"), nullable=False, index=True)
    
    side = Column(Enum(PositionSide), nullable=False)
    leverage = Column(Numeric(8, 4), nullable=False)
    entry_price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    margin_used = Column(Numeric(18, 2), nullable=False)
    liquidation_price = Column(Numeric(18, 4), nullable=False)
    
    status = Column(Enum(PositionStatus), default=PositionStatus.OPEN, nullable=False, index=True)
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    exit_price = Column(Numeric(18, 4))
    realized_pnl = Column(Numeric(18, 2))

    user = relationship("User")
    stock = relationship("Stock")
