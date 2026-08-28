import json
import time
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
import uvicorn

from app.config import QUEUE_KEY, EVENT_STORE_PREFIX
from app.extractors import extract_event_id
from app.redis import get_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    await get_redis()
    yield
    # Teardown
    await close_redis()

app = FastAPI(title="Webhook Receiver", lifespan=lifespan)

@app.post("/webhooks/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(provider: str, request: Request) -> Response:
    # 1. Parse and validate JSON body
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Request body cannot be empty"}
            )
        payload = json.loads(body_bytes)
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Webhook payload must be a JSON object"}
            )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid JSON body"}
        )

    # 2. Extract Event ID
    event_id = extract_event_id(provider, payload, request.headers)
    if not event_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "No recognizable event ID in payload or headers"}
        )

    # 3. Enqueue and acknowledge immediately
    redis = await get_redis()
    message = {
        "event_id": event_id,
        "provider": provider,
        "payload": payload,
        "attempt": 0,
        "enqueued_at": time.time(),
    }
    
    # Store initial event record and push to queue
    await redis.hset(
        f"{EVENT_STORE_PREFIX}{event_id}",
        mapping={"status": "pending", "attempts": "0", "provider": provider}
    )
    await redis.rpush(QUEUE_KEY, json.dumps(message))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted", "event_id": event_id}
    )
