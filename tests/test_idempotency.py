import asyncio
import uuid
import pytest
from app.idempotency import (
    claim_event,
    mark_event_done,
    release_claim,
    ClaimAlreadyHeldError,
    EventAlreadyDoneError
)
from app.redis import get_redis

import pytest_asyncio

@pytest_asyncio.fixture
async def redis():
    r = await get_redis()
    yield r
    # Could flush db, but better to use random keys

def gen_event_id():
    return str(uuid.uuid4())

@pytest.mark.asyncio
async def test_claim_succeeds_and_mark_done(redis):
    event_id = gen_event_id()
    
    # Claim succeeds
    claimed = await claim_event(redis, event_id)
    assert claimed is True
    
    # Mark done
    await mark_event_done(redis, event_id)
    
    # Cannot claim again, it's done
    with pytest.raises(EventAlreadyDoneError):
        await claim_event(redis, event_id)

@pytest.mark.asyncio
async def test_claim_already_held(redis):
    event_id = gen_event_id()
    
    # First claim succeeds
    await claim_event(redis, event_id)
    
    # Second claim fails
    with pytest.raises(ClaimAlreadyHeldError):
        await claim_event(redis, event_id)
        
    # Release claim
    await release_claim(redis, event_id)
    
    # Can claim again
    assert await claim_event(redis, event_id) is True

@pytest.mark.asyncio
async def test_concurrency_race_condition(redis):
    event_id = gen_event_id()
    
    # Spin up 10 concurrent claim attempts
    async def try_claim():
        try:
            return await claim_event(redis, event_id)
        except (ClaimAlreadyHeldError, EventAlreadyDoneError):
            return False

    results = await asyncio.gather(*(try_claim() for _ in range(10)))
    
    # Exactly one should be True, the rest False
    successes = [r for r in results if r is True]
    assert len(successes) == 1

@pytest.mark.asyncio
async def test_duplicate_delivery_is_noop(redis):
    event_id = gen_event_id()
    
    # Manually mark as done (as if it was processed)
    await mark_event_done(redis, event_id)
    
    # New delivery arrives and tries to claim
    with pytest.raises(EventAlreadyDoneError):
        await claim_event(redis, event_id)

@pytest.mark.asyncio
async def test_crashed_worker_reclaim(redis):
    event_id = gen_event_id()
    
    # Force a very short TTL for testing
    import app.idempotency
    original_ttl = app.idempotency.CLAIM_TTL
    app.idempotency.CLAIM_TTL = 1
    
    try:
        # First worker claims
        await claim_event(redis, event_id)
        
        # Second worker immediately fails
        with pytest.raises(ClaimAlreadyHeldError):
            await claim_event(redis, event_id)
            
        # Wait for TTL to expire
        await asyncio.sleep(1.1)
        
        # Second worker re-attempts and succeeds
        assert await claim_event(redis, event_id) is True
    finally:
        app.idempotency.CLAIM_TTL = original_ttl
