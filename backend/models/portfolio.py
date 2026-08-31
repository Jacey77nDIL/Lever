import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    cash_balance = Column(Numeric(18, 2), nullable=False)
    positions_value = Column(Numeric(18, 2), nullable=False)
    total_equity = Column(Numeric(18, 2), nullable=False)
    
    captured_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    user = relationship("User")

class OpenInterest(Base):
    __tablename__ = "open_interest"

    symbol = Column(String(20), ForeignKey("stocks.symbol"), primary_key=True)
    total_long_shares = Column(Numeric(18, 4), default=0.0, nullable=False)
    total_short_shares = Column(Numeric(18, 4), default=0.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    stock = relationship("Stock")
