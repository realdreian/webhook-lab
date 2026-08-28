import json
import time
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis import get_redis
from app.config import QUEUE_KEY, EVENT_STORE_PREFIX
from worker.worker_loop import worker_loop

@pytest_asyncio.fixture
async def redis():
    r = await get_redis()
    yield r

def gen_event_id():
    return str(uuid.uuid4())

@pytest.mark.asyncio
async def test_e2e_visibility_retry_flow(redis):
    # 6.4: Send webhook event with "fail": true, run worker, confirm GET /events status
    event_id = gen_event_id()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest event
        response = await client.post(
            "/webhooks/stripe",
            json={"event_id": event_id, "fail": True}
        )
        assert response.status_code == 202
        
        # 2. Check initial pending status
        response_events = await client.get("/events")
        assert response_events.status_code == 200
        events_list = response_events.json()
        target = next((e for e in events_list if e["event_id"] == event_id), None)
        assert target is not None
        assert target["status"] == "pending"
        assert target["attempts"] == 0

        # 3. Run worker loop once to process
        await worker_loop(redis, once=True)

        # 4. Check status is updated to failed/retrying with attempts = 1
        response_events2 = await client.get("/events")
        events_list2 = response_events2.json()
        target2 = next((e for e in events_list2 if e["event_id"] == event_id), None)
        assert target2 is not None
        assert target2["status"] == "failed/retrying"
        assert target2["attempts"] == 1
