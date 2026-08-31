import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Integer, Boolean, DateTime, ForeignKey, Enum, BigInteger
from sqlalchemy.orm import relationship
from core.database import Base

class LiquidityTier(str, enum.Enum):
    BLUE_CHIP = "BLUE_CHIP"
    ESTABLISHED = "ESTABLISHED"
    VOLATILE = "VOLATILE"
    RESTRICTED = "RESTRICTED"

class Stock(Base):
    __tablename__ = "stocks"

    symbol = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    shares_outstanding = Column(BigInteger)
    current_price = Column(Numeric(18, 4))
    change_percent = Column(Numeric(8, 4))
    volume = Column(BigInteger)
    pe_ratio = Column(Numeric(18, 4))
    
    liquidity_tier = Column(Enum(LiquidityTier), default=LiquidityTier.RESTRICTED, nullable=False)
    margin_requirement = Column(Numeric(8, 4), default=1.0)
    max_leverage = Column(Numeric(8, 4), default=1.0)
    shortable = Column(Boolean, default=False)
    
    tier_last_computed_at = Column(DateTime(timezone=True))
    listed_since = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class StockPriceSnapshot(Base):
    __tablename__ = "stock_price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), ForeignKey("stocks.symbol"), nullable=False, index=True)
    price = Column(Numeric(18, 4), nullable=False)
    change_percent = Column(Numeric(8, 4))
    volume = Column(BigInteger)
    captured_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    stock = relationship("Stock")
