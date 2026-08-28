import asyncio
from redis.asyncio import Redis, from_url
from app.config import REDIS_URL

_redis_client: Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None

async def get_redis() -> Redis:
    global _redis_client, _client_loop
    current_loop = asyncio.get_running_loop()
    if _redis_client is None or _client_loop != current_loop:
        _redis_client = from_url(REDIS_URL, decode_responses=True)
        _client_loop = current_loop
    return _redis_client

async def close_redis() -> None:
    global _redis_client, _client_loop
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
        _client_loop = None
