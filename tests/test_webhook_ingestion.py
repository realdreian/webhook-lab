import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.extractors import extract_event_id

@pytest.mark.asyncio
async def test_extract_event_id_headers_and_payload():
    # Header takes priority or is found
    assert extract_event_id("stripe", {}, {"x-webhook-id": "hdr_123"}) == "hdr_123"
    assert extract_event_id("github", {}, {"x-github-delivery": "gh_delivery_1"}) == "gh_delivery_1"
    assert extract_event_id("generic", {}, {"x-event-id": "evt_hdr"}) == "evt_hdr"
    
    # Payload fields
    assert extract_event_id("generic", {"event_id": "evt_field"}, {}) == "evt_field"
    assert extract_event_id("stripe", {"id": "evt_stripe_id"}, {}) == "evt_stripe_id"
    assert extract_event_id("github", {"delivery_id": "evt_gh_field"}, {}) == "evt_gh_field"

    # Missing ID
    assert extract_event_id("generic", {"unrelated": "data"}, {}) is None
    assert extract_event_id("generic", {}, {}) is None

@pytest.mark.asyncio
async def test_malformed_json_body_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid JSON string
        response = await client.post(
            "/webhooks/stripe",
            content="invalid-json-content{",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

        # Empty body
        response = await client.post(
            "/webhooks/stripe",
            content="",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

        # JSON array instead of object
        response = await client.post(
            "/webhooks/stripe",
            content="[1, 2, 3]",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_missing_event_id_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/generic",
            json={"data": "no-id-here"}
        )
        assert response.status_code == 400
        assert "No recognizable event ID" in response.json()["detail"]

@pytest.mark.asyncio
async def test_blank_event_id_is_not_usable_and_returns_400():
    # An event ID field that is present but empty/whitespace-only is not a
    # "usable event ID" per spec, so it must be treated as if no ID was
    # supplied at all (400, nothing enqueued) -- not accepted as a literal
    # blank identifier.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Blank event_id in the payload
        response = await client.post(
            "/webhooks/generic",
            json={"event_id": "   ", "type": "noop"}
        )
        assert response.status_code == 400
        assert "No recognizable event ID" in response.json()["detail"]

        # Blank event ID in the header, with no usable payload field
        response = await client.post(
            "/webhooks/generic",
            headers={"X-Event-Id": "   "},
            json={"type": "noop"}
        )
        assert response.status_code == 400
        assert "No recognizable event ID" in response.json()["detail"]

@pytest.mark.asyncio
async def test_valid_event_id_in_payload_returns_2xx():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/stripe",
            json={"event_id": "evt_unit_test_1", "type": "payment.succeeded"}
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == "evt_unit_test_1"

@pytest.mark.asyncio
async def test_valid_event_id_in_header_returns_2xx():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/github",
            headers={"X-GitHub-Delivery": "gh_unit_test_2"},
            json={"action": "push"}
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == "gh_unit_test_2"

@pytest.mark.asyncio
async def test_get_events_endpoint():
    from app.redis import get_redis
    from app.config import EVENT_STORE_PREFIX
    redis = await get_redis()
    
    # Pre-populate an event
    test_id = "test_get_events_id"
    await redis.hset(
        f"{EVENT_STORE_PREFIX}{test_id}",
        mapping={"status": "processing", "attempts": "2", "provider": "stripe"}
    )
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/events")
        assert response.status_code == 200
        events_list = response.json()
        assert isinstance(events_list, list)
        
        # Verify the target event is present and has the correct shape
        target_event = next((e for e in events_list if e["event_id"] == test_id), None)
        assert target_event is not None
        assert target_event["status"] == "processing"
        assert target_event["attempts"] == 2

@pytest.mark.asyncio
async def test_static_page_serves_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check root page returns HTML
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Webhook Event List" in response.text

        # Check static mount serves index.html
        response_static = await client.get("/static/index.html")
        assert response_static.status_code == 200
        assert "text/html" in response_static.headers.get("content-type", "")
        assert "Webhook Event List" in response_static.text
