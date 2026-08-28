import json
import asyncio
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis import get_redis
from app.config import QUEUE_KEY, DELAYED_QUEUE_KEY, EVENT_STORE_PREFIX, IDEMPOTENCY_PREFIX
from worker.worker_loop import worker_loop
import worker.worker_loop

@pytest_asyncio.fixture
async def redis():
    r = await get_redis()
    await r.delete(QUEUE_KEY)
    await r.delete(DELAYED_QUEUE_KEY)
    yield r

def gen_event_id():
    return str(uuid.uuid4())

@pytest.mark.asyncio
async def test_concurrent_duplicate_ingestion_processed_once(redis):
    # Send the same event ID twice concurrently, and verify processing logic executes exactly once
    event_id = gen_event_id()
    
    # We will wrap process_event_stub to count executions
    execution_count = 0
    original_process = worker.worker_loop.process_event_stub
    
    async def mock_process(evt, r):
        nonlocal execution_count
        execution_count += 1
        await original_process(evt, r)
        
    worker.worker_loop.process_event_stub = mock_process
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest twice concurrently
        responses = await asyncio.gather(
            client.post("/webhooks/stripe", json={"event_id": event_id}),
            client.post("/webhooks/stripe", json={"event_id": event_id})
        )
        for r in responses:
            assert r.status_code == 202
            
        # Run worker loop to process both items in the queue
        await worker_loop(redis, once=True)
        await worker_loop(redis, once=True)
        
    worker.worker_loop.process_event_stub = original_process
    
    # Assert processing logic was executed exactly once
    assert execution_count == 1
    
    # Check final state
    record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
    assert record.get("status") == "succeeded"

@pytest.mark.asyncio
async def test_failure_retry_success_flow(redis):
    # Simulate a processing failure followed by a successful retry, and verify the event is marked done exactly once and not reprocessed after success
    event_id = gen_event_id()
    
    execution_calls = []
    original_process = worker.worker_loop.process_event_stub
    
    async def mock_process(evt, r):
        execution_calls.append(evt["event_id"])
        if len(execution_calls) == 1:
            raise Exception("Temporary processing error")
        await original_process(evt, r)
        
    worker.worker_loop.process_event_stub = mock_process
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest event
        response = await client.post("/webhooks/stripe", json={"event_id": event_id})
        assert response.status_code == 202
        
        # 2. Run worker loop (first attempt fails)
        await worker_loop(redis, once=True)
        
        # Check status is failed/retrying
        record1 = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
        assert record1.get("status") == "failed/retrying"
        
        # Confirm it's in the delayed queue
        delayed_items = await redis.zrange(DELAYED_QUEUE_KEY, 0, -1)
        target_item = None
        for item in delayed_items:
            parsed = json.loads(item)
            if parsed["event_id"] == event_id:
                target_item = item
                break
        assert target_item is not None
        
        # 3. Simulate time passing by modifying the delayed queue score to 0 (ready now)
        await redis.zadd(DELAYED_QUEUE_KEY, {target_item: 0})
        
        # 4. Run worker loop again (this will fetch the delayed item and process it; the second attempt succeeds)
        await worker_loop(redis, once=True)
        
        # Check status is succeeded
        record2 = await redis.hgetall(f"{EVENT_STORE_PREFIX}{event_id}")
        assert record2.get("status") == "succeeded"
        
        # Verify idempotency key is set to "done"
        val = await redis.get(f"{IDEMPOTENCY_PREFIX}{event_id}")
        assert val == "done"
        
        # 5. Simulate duplicate delivery (e.g. manually enqueueing it again)
        # Push it back to main queue
        await redis.rpush(QUEUE_KEY, target_item)
        
        # Run worker loop a third time
        await worker_loop(redis, once=True)
        
    worker.worker_loop.process_event_stub = original_process
    
    # Assert it was only processed/called twice (1st failed, 2nd succeeded), not 3 times.
    assert len(execution_calls) == 2
