import json
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
