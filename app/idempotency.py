from typing import Optional
from redis.asyncio import Redis
from app.config import IDEMPOTENCY_PREFIX, CLAIM_TTL, DONE_TTL

class IdempotencyError(Exception):
    pass

class ClaimAlreadyHeldError(IdempotencyError):
    pass

class EventAlreadyDoneError(IdempotencyError):
    pass

async def claim_event(redis: Redis, event_id: str) -> bool:
    """
    Attempts to claim an event for processing.
    Returns True if successfully claimed.
    Raises ClaimAlreadyHeldError if another worker is currently processing it.
    Raises EventAlreadyDoneError if the event was already processed.
    """
    key = f"{IDEMPOTENCY_PREFIX}{event_id}"
    
    # Check if it's already done
    val = await redis.get(key)
    if val == "done":
        raise EventAlreadyDoneError(f"Event {event_id} is already done.")
    
    # Try to claim
    # SET NX EX
    claimed = await redis.set(key, "claimed", nx=True, ex=CLAIM_TTL)
    if not claimed:
        # It's either claimed by someone else, or just marked done in the split second
        val = await redis.get(key)
        if val == "done":
            raise EventAlreadyDoneError(f"Event {event_id} is already done.")
        else:
            raise ClaimAlreadyHeldError(f"Event {event_id} is currently claimed by another worker.")
            
    return True

async def mark_event_done(redis: Redis, event_id: str) -> None:
    """
    Marks an event as successfully processed.
    """
    key = f"{IDEMPOTENCY_PREFIX}{event_id}"
    await redis.set(key, "done", ex=DONE_TTL)

async def release_claim(redis: Redis, event_id: str) -> None:
    """
    Releases a claim (e.g. on failure) so it can be retried later.
    Only releases if the current value is 'claimed' (not 'done').
    """
    key = f"{IDEMPOTENCY_PREFIX}{event_id}"
    
    # We could use a Lua script to be strictly atomic, but since 
    # we only release on failure, a GET then DEL if "claimed" is usually acceptable.
    # A Lua script is safer:
    lua_script = """
    if redis.call("get", KEYS[1]) == "claimed" then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    await redis.eval(lua_script, 1, key)
