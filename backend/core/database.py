from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import redis.asyncio as redis
from .config import settings

# SQLAlchemy setup
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,
    connect_args={"prepared_statement_cache_size": 0, "statement_cache_size": 0}
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

from upstash_redis.asyncio import Redis as UpstashRedis

# Redis setup
if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
    redis_client = UpstashRedis(
        url=settings.UPSTASH_REDIS_REST_URL, 
        token=settings.UPSTASH_REDIS_REST_TOKEN
    )
else:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis():
    return redis_client
