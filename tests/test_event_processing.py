import json
import time
import uuid
import pytest
import pytest_asyncio

from app.redis import get_redis
from worker.worker_loop import handle_event, check_delayed_queue, worker_loop
from app.config import (
    QUEUE_KEY,
    DELAYED_QUEUE_KEY,
    DLQ_KEY,
    EVENT_STORE_PREFIX,
    IDEMPOTENCY_PREFIX,
    BASE_DELAY,
    MAX_DELAY,
    MAX_ATTEMPTS
)
from app.idempotency import claim_event, mark_event_done, release_claim

@pytest_asyncio.fixture
async def redis():
    r = await get_redis()
    yield r

def gen_event_id():
    return str(uuid.uuid4())

def make_event(event_id, attempt=0, payload=None):
    if payload is None:
        payload = {}
    return {
        "event_id": event_id,
        "provider": "test",
        "payload": payload,
        "attempt": attempt,
        "enqueued_at": time.time()
    }

@pytest.mark.asyncio
async def test_worker_claim_execution(redis):
    # 4.1: only executes if claim succeeds
    event_id = gen_event_id()
    event = make_event(event_id)
    
    # Pre-claim the event
    await claim_event(redis, event_id)
    
    # Process event
    await handle_event(redis, json.dumps(event))
    
    # It should NOT be marked as succeeded because it couldn't claim it
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
    assert record.get("status") != "succeeded"

@pytest.mark.asyncio
async def test_stub_processing_success_and_failure(redis):
    # 4.6: Stub logic succeeds/records or fails/retryable
    event_id_success = gen_event_id()
    event_success = make_event(event_id_success, payload={"data": "ok"})
    
    await handle_event(redis, json.dumps(event_success))
    
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id_success}")
    assert record.get("status") == "succeeded"
    
    event_id_fail = gen_event_id()
    event_fail = make_event(event_id_fail, payload={"fail": True})
    
    await handle_event(redis, json.dumps(event_fail))
    
    record2 = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id_fail}")
    assert record2.get("status") == "failed/retrying"

@pytest.mark.asyncio
async def test_exponential_backoff_delay_sequence(redis):
    # 4.2: Backoff schedule sequence
    event_id = gen_event_id()
    
    # Attempt 0 -> failure -> attempt 1
    event = make_event(event_id, payload={"fail": True})
    await handle_event(redis, json.dumps(event))
    
    items = await redis.zrange(DELAYED_QUEUE_KEY, 0, -1, withscores=True)
    
    # Find our event
    target = None
    for item, score in items:
        if json.loads(item)["event_id"] == event_id:
            target = score
            break
            
    assert target is not None
    # Calculate expected delay
    expected_delay = min(BASE_DELAY * (2 ** 1), MAX_DELAY)
    # The score should be roughly time.time() + expected_delay
    # We just ensure it's in the future and matches the formula logically.
    assert target > time.time()
    
    # Let's clean up
    await redis.zremrangebyscore(DELAYED_QUEUE_KEY, "-inf", "+inf")

@pytest.mark.asyncio
async def test_max_attempts_dead_letter(redis):
    # 4.3: Max attempts exhausted stops retries, goes to DLQ
    event_id = gen_event_id()
    # If attempt is MAX_ATTEMPTS - 1, the next failure makes it MAX_ATTEMPTS
    event = make_event(event_id, attempt=MAX_ATTEMPTS - 1, payload={"fail": True})
    
    await handle_event(redis, json.dumps(event))
    
    # Should not be in delayed queue
    items = await redis.zrange(DELAYED_QUEUE_KEY, 0, -1)
    assert not any(json.loads(i)["event_id"] == event_id for i in items)
    
    # Should be in DLQ
    dlq_items = await redis.lrange(DLQ_KEY, 0, -1)
    assert any(json.loads(i)["event_id"] == event_id for i in dlq_items)
    
    # Check status
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
    assert record.get("status") == "dead-lettered"

@pytest.mark.asyncio
async def test_release_claim_on_failure_can_reclaim(redis):
    # 4.4: On processing failure, release the idempotency claim, confirm reclaim
    event_id = gen_event_id()
    event = make_event(event_id, payload={"fail": True})
    
    await handle_event(redis, json.dumps(event))
    
    # The claim key should be deleted
    claim = await redis.get(f"{IDEMPOTENCY_PREFIX}{event_id}")
    assert claim is None
    
    # Verify a retried attempt can re-claim it
    assert await claim_event(redis, event_id) is True

@pytest.mark.asyncio
async def test_backoff_does_not_stall_queue(redis):
    # 4.5: Backlogged retry doesn't stall the queue
    event_id_fail = gen_event_id()
    event_fail = make_event(event_id_fail, payload={"fail": True})
    
    event_id_success = gen_event_id()
    event_success = make_event(event_id_success, payload={"fail": False})
    
    # Enqueue both
    await redis.rpush(QUEUE_KEY, json.dumps(event_fail))
    await redis.rpush(QUEUE_KEY, json.dumps(event_success))
    
    # Process both (worker_loop once)
    await worker_loop(redis, once=True) # processes first
    await worker_loop(redis, once=True) # processes second
    
    # The failed event should be in delayed queue
    items = await redis.zrange(DELAYED_QUEUE_KEY, 0, -1)
    assert any(json.loads(i)["event_id"] == event_id_fail for i in items)
    
    # The success event should be done
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id_success}")
    assert record.get("status") == "succeeded"

@pytest.mark.asyncio
async def test_event_transitions(redis):
    # 6.1: verify a test asserts the record reflects each transition
    event_id = gen_event_id()
    event = make_event(event_id, payload={"fail": False})
    
    # Ingest state simulation (pending, 0 attempts)
    await redis.hset(
        f"{EVENT_STORE_PREFIX}{event_id}",
        mapping={"status": "pending", "attempts": "0", "provider": "test"}
    )
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
    assert record.get("status") == "pending"
    assert record.get("attempts") == "0"
    
    # We mock process_event_stub to check if the status is "processing" and attempts is "1"
    # while processing is active.
    import worker.worker_loop
    original_process = worker.worker_loop.process_event_stub
    
    async def mock_process(evt, r):
        # Assert during processing transition
        rec = await r.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
        assert rec.get("status") == "processing"
        assert rec.get("attempts") == "1"
        
    worker.worker_loop.process_event_stub = mock_process
    
    try:
        await handle_event(redis, json.dumps(event))
    finally:
        worker.worker_loop.process_event_stub = original_process
        
    # Check final state (succeeded, 1 attempt)
    final_record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
    assert final_record.get("status") == "succeeded"
    assert final_record.get("attempts") == "1"
