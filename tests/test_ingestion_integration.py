import json
import time
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.redis import get_redis
from app.config import QUEUE_KEY, EVENT_STORE_PREFIX

@pytest.mark.asyncio
async def test_enqueue_and_acknowledge_flow():
    """Verify that incoming webhooks are enqueued in Redis and acknowledged immediately (2xx) before processing."""
    redis = await get_redis()
    # Clean up test keys
    test_event_id = f"evt_flow_{int(time.time() * 1000)}"
    test_queue_key = QUEUE_KEY
    await redis.delete(test_queue_key)
    await redis.delete(f"{EVENT_STORE_PREFIX}{test_event_id}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_time = time.time()
        response = await client.post(
            "/webhooks/stripe",
            json={"event_id": test_event_id, "amount": 1000, "currency": "usd"}
        )
        duration = time.time() - start_time

        # Response must return quickly with 2xx
        assert response.status_code == 202
        assert duration < 0.5  # Returns fast without waiting for downstream processing
        data = response.json()
        assert data["event_id"] == test_event_id
        assert data["status"] == "accepted"

        # Assert event is placed in Redis queue
        queue_len = await redis.llen(test_queue_key)
        assert queue_len >= 1
        
        # Pop or peek the queue to verify contents
        item = await redis.lindex(test_queue_key, -1)
        assert item is not None
        parsed_item = json.loads(item)
        assert parsed_item["event_id"] == test_event_id
        assert parsed_item["provider"] == "stripe"
        assert parsed_item["payload"]["amount"] == 1000
        assert parsed_item["attempt"] == 0

        # Assert initial event record was written
        event_record = await redis.hgetall(f"{EVENT_STORE_PREFIX}{test_event_id}")
        assert event_record["status"] == "pending"
        assert event_record["attempts"] == "0"
        assert event_record["provider"] == "stripe"

@pytest.mark.asyncio
async def test_queue_accepts_event_under_processing_backlog():
    """Verify that ingestion still accepts and acks new events when queue has a backlog."""
    redis = await get_redis()
    
    # 1. Simulate a large backlog by pushing multiple dummy items into the queue
    test_queue_key = QUEUE_KEY
    await redis.delete(test_queue_key)
    
    backlog_items = [
        json.dumps({"event_id": f"backlog_evt_{i}", "provider": "test", "payload": {}, "attempt": 0})
        for i in range(100)
    ]
    await redis.rpush(test_queue_key, *backlog_items)
    
    initial_len = await redis.llen(test_queue_key)
    assert initial_len == 100

    # 2. Ingest a new event
    new_event_id = f"evt_new_during_backlog_{int(time.time() * 1000)}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_time = time.time()
        response = await client.post(
            "/webhooks/github",
            headers={"X-GitHub-Delivery": new_event_id},
            json={"ref": "refs/heads/main"}
        )
        duration = time.time() - start_time

        # Must succeed with 2xx immediately despite backlog
        assert response.status_code == 202
        assert duration < 0.5
        assert response.json()["event_id"] == new_event_id

        # Queue length must now be 101
        new_len = await redis.llen(test_queue_key)
        assert new_len == 101

        # The last item in queue should be the new event
        last_item = await redis.lindex(test_queue_key, -1)
        assert last_item is not None
        parsed_last = json.loads(last_item)
        assert parsed_last["event_id"] == new_event_id
