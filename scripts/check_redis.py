import asyncio
import sys
import redis.asyncio as redis

async def check_redis():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        pong = await client.ping()
        if not pong:
            print("Error: Redis ping failed.")
            sys.exit(1)
        print("Redis ping successful: PONG")

        config = await client.config_get("appendonly")
        appendonly = config.get("appendonly")
        print(f"Redis appendonly config: {appendonly}")
        if appendonly != "yes":
            print("Warning / Error: Redis appendonly is not 'yes'.")
            sys.exit(1)
        print("Redis health check passed: connectivity OK and AOF (appendonly) is enabled.")
    except Exception as e:
        print(f"Health check failed with error: {e}")
        sys.exit(1)
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(check_redis())
