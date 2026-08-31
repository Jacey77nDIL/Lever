from decimal import Decimal
from models.position import PositionSide
from models.stock import LiquidityTier
from core.config import settings

def get_spread_for_tier(tier: LiquidityTier) -> Decimal:
    if tier == LiquidityTier.BLUE_CHIP:
        return settings.SPREAD_BLUE_CHIP
    elif tier == LiquidityTier.ESTABLISHED:
        return settings.SPREAD_ESTABLISHED
    elif tier == LiquidityTier.VOLATILE:
        return settings.SPREAD_VOLATILE
    else:
        return settings.SPREAD_RESTRICTED

def compute_execution_price(mid_price: Decimal, side: PositionSide, action_is_open: bool, tier: LiquidityTier) -> Decimal:
    """
    Opening a long or closing a short buys at mid_price * (1 + spread/2)
    Opening a short or closing a long sells at mid_price * (1 - spread/2)
    """
    spread = get_spread_for_tier(tier)
    
    if (side == PositionSide.LONG and action_is_open) or (side == PositionSide.SHORT and not action_is_open):
        return mid_price * (Decimal("1") + spread / Decimal("2"))
    else:
        return mid_price * (Decimal("1") - spread / Decimal("2"))

def compute_liquidation_price(entry_price: Decimal, side: PositionSide, initial_margin_fraction: Decimal, leverage: Decimal) -> Decimal:
    """
    Computes the price at which the position's remaining equity falls to maintenance margin level.
    Maintenance margin is a fraction of the initial margin requirement.
    """
    maintenance_margin_fraction = initial_margin_fraction * settings.MAINTENANCE_MARGIN_FRACTION
    
    # formula derivation:
    # unrealized_pnl = (current - entry) * quantity * sign
    # margin_used = amount = entry * quantity / leverage
    # equity = margin_used + unrealized_pnl
    # liquidation happens when equity <= maintenance_margin_fraction * notional
    # notional = entry * quantity
    # margin_used + (current - entry) * quantity * sign <= maintenance_margin_fraction * entry * quantity
    # divide by quantity:
    # (entry / leverage) + (current - entry) * sign <= maintenance_margin_fraction * entry
    
    if side == PositionSide.LONG:
        # current <= entry - (entry / leverage) + maintenance_margin_fraction * entry + entry
        # current <= entry * (1 - (1/leverage) + maintenance_margin_fraction)
        return entry_price * (Decimal("1") - (Decimal("1") / leverage) + maintenance_margin_fraction)
    else:
        # (entry / leverage) - (current - entry) <= maintenance_margin_fraction * entry
        # current >= entry * (1 + (1/leverage) - maintenance_margin_fraction)
        return entry_price * (Decimal("1") + (Decimal("1") / leverage) - maintenance_margin_fraction)
