from pydantic_settings import BaseSettings, SettingsConfigDict
from decimal import Decimal

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lever API"
    
    # DB Settings
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    
    # Kobo Terminal API
    KOBO_API_KEY: str
    KOBO_API_BASE_URL: str = "https://koboterminal.com"

    # Trading Rules
    STARTING_CASH: Decimal = Decimal("10000.00")
    
    # Open Interest Caps
    OPEN_INTEREST_CAP_PCT: Decimal = Decimal("0.05") # 5% of shares outstanding
    MAX_ORDER_PCT_OF_ADV: Decimal = Decimal("0.02") # 2% of average daily value traded
    MAX_POSITION_PCT_OF_EQUITY: Decimal = Decimal("0.50") # 50% of user's total equity
    MAINTENANCE_MARGIN_FRACTION: Decimal = Decimal("0.50") # 50% of initial margin

    # Liquidity Tier Spread Adjustments
    SPREAD_BLUE_CHIP: Decimal = Decimal("0.0015")
    SPREAD_ESTABLISHED: Decimal = Decimal("0.0035")
    SPREAD_VOLATILE: Decimal = Decimal("0.0075")
    SPREAD_RESTRICTED: Decimal = Decimal("0.0150")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
