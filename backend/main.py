from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import contextlib

from api import auth, market, trading, portfolio
from services.ingestion import start_scheduler
from core.database import engine, redis_client
from core.config import settings

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    await engine.dispose()
    await redis_client.aclose()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(market.router, prefix="/market", tags=["market"])
# Map /stocks to market router natively without prefix to match prompt
app.include_router(market.router, tags=["market"]) # includes /stocks
app.include_router(trading.router, tags=["trading"]) # includes /positions, /trades
app.include_router(portfolio.router, tags=["portfolio"]) # includes /portfolio, /leaderboard
