import asyncio
from app.redis import get_redis, close_redis
from worker.worker_loop import worker_loop

async def main():
    print("Worker starting...")
    redis = await get_redis()
    try:
        await worker_loop(redis)
    finally:
        await close_redis()
        print("Worker stopped.")

if __name__ == "__main__":
    asyncio.run(main())
