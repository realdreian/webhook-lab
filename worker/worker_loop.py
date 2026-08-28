import asyncio
import json
import time
from redis.asyncio import Redis

from app.config import (
    QUEUE_KEY,
    DELAYED_QUEUE_KEY,
    DLQ_KEY,
    BASE_DELAY,
    MAX_DELAY,
    MAX_ATTEMPTS,
    EVENT_STORE_PREFIX
)
from app.idempotency import (
    claim_event,
    release_claim,
    mark_event_done,
    ClaimAlreadyHeldError,
    EventAlreadyDoneError
)

class ProcessingFailure(Exception):
    pass

async def process_event_stub(event: dict, redis: Redis):
    """
    Stub processing logic.
    Raises ProcessingFailure if payload contains "fail": true.
    Otherwise, writes success record.
    """
    payload = event.get("payload", {})
    if isinstance(payload, dict) and payload.get("fail") is True:
        raise ProcessingFailure("Deliberate failure triggered by payload")
    
    # Write success record to event-record store
    event_id = event["event_id"]
    await redis.hset(
        f"{EVENT_STORE_PREFIX}{event_id}",
        mapping={"status": "succeeded", "attempts": str(event.get("attempt", 0))}
    )

async def handle_event(redis: Redis, event_str: str):
    event = json.loads(event_str)
    event_id = event["event_id"]
    
    try:
        # Attempt claim
        await claim_event(redis, event_id)
    except (ClaimAlreadyHeldError, EventAlreadyDoneError):
        # Already processed or being processed by another worker
        return

    try:
        # Increment attempts and set status to processing
        current_attempt = event.get("attempt", 0) + 1
        event["attempt"] = current_attempt
        
        await redis.hset(
            f"{EVENT_STORE_PREFIX}{event_id}",
            mapping={"status": "processing", "attempts": str(current_attempt)}
        )
        
        # Execute processing logic
        await process_event_stub(event, redis)
        # Mark done
        await mark_event_done(redis, event_id)
        
        await redis.hset(
            f"{EVENT_STORE_PREFIX}{event_id}",
            mapping={"status": "succeeded", "attempts": str(current_attempt)}
        )
        
    except Exception as e:
        # Release claim on failure
        await release_claim(redis, event_id)
        
        # Max attempts enforcement
        attempt = event["attempt"]
        if attempt >= MAX_ATTEMPTS:
            await redis.rpush(DLQ_KEY, json.dumps(event))
            await redis.hset(
                f"{EVENT_STORE_PREFIX}{event_id}",
                mapping={"status": "dead-lettered", "attempts": str(attempt)}
            )
        else:
            # Exponential backoff
            delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            ready_at = time.time() + delay
            await redis.zadd(DELAYED_QUEUE_KEY, {json.dumps(event): ready_at})
            await redis.hset(
                f"{EVENT_STORE_PREFIX}{event_id}",
                mapping={"status": "failed/retrying", "attempts": str(attempt)}
            )

async def check_delayed_queue(redis: Redis):
    """
    Moves ready items from delayed queue to the main queue.
    """
    now = time.time()
    # Find items that are ready
    ready_items = await redis.zrangebyscore(DELAYED_QUEUE_KEY, 0, now)
    if ready_items:
        # Move them to the main queue
        for item in ready_items:
            if await redis.zrem(DELAYED_QUEUE_KEY, item):
                await redis.rpush(QUEUE_KEY, item)

async def worker_loop(redis: Redis, once: bool = False):
    """
    Main worker loop. Polls delayed queue, then main queue.
    """
    while True:
        await check_delayed_queue(redis)
        
        # Pop from main queue (non-blocking for easy testing, or short timeout)
        event_str = await redis.lpop(QUEUE_KEY)
        if event_str:
            await handle_event(redis, event_str)
        else:
            if once:
                break
            await asyncio.sleep(0.1)
