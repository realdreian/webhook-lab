import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

QUEUE_KEY = os.getenv("QUEUE_KEY", "queue:events")
EVENT_STORE_PREFIX = os.getenv("EVENT_STORE_PREFIX", "event:")
IDEMPOTENCY_PREFIX = os.getenv("IDEMPOTENCY_PREFIX", "idempotency:")
