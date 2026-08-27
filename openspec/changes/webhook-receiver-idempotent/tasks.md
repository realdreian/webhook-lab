## 1. Project setup

- [x] 1.1 Initialize Python project structure (FastAPI app package, worker entrypoint, `pyproject.toml`/`requirements.txt`) and verify `python -m app` (or equivalent) imports cleanly
- [ ] 1.2 Add FastAPI, Redis client (e.g. `redis-py` with async support), and test dependencies (pytest, pytest-asyncio) and verify `pip install` / dependency resolution succeeds
- [ ] 1.3 Verify connectivity to the already-running local Redis instance (`localhost:6379`) with a health-check script, and confirm AOF persistence is enabled (e.g. `redis-cli CONFIG GET appendonly` returns `yes`) — no docker-compose and no Redis install needed, Redis is already installed and running locally

## 2. Webhook ingestion (specs/webhook-ingestion)

- [ ] 2.1 Implement `POST /webhooks/{provider}` handler that parses and validates the JSON body, and verify a unit test covers the malformed-body → `400` scenario
- [ ] 2.2 Implement event ID extraction (payload field and/or header, per provider config) and verify a unit test covers both the "ID present" and "ID missing → 400" scenarios
- [ ] 2.3 Implement enqueue-and-acknowledge flow (write event + event ID to the Redis queue, respond `2xx` before processing) and verify an integration test asserts the response returns before the event is processed
- [ ] 2.4 Verify a load/backlog test confirms ingestion still accepts and acks new events while the queue has a backlog (spec: "Queue accepts event under processing backlog")

## 3. Idempotency store (specs/event-idempotency)

- [ ] 3.1 Implement claim/release helper using Redis `SET NX EX` for claiming an event ID and `SET EX` for marking it done, and verify unit tests cover claim-succeeds, claim-already-held, and mark-done transitions
- [ ] 3.2 Wire claim TTL and done-record TTL to configuration values and verify they are read from environment/config, not hardcoded
- [ ] 3.3 Write a concurrency test that spins up two simultaneous claim attempts for the same event ID and verifies exactly one succeeds (spec: "Two workers race on the same event ID")
- [ ] 3.4 Write a test that simulates a completed event being redelivered and verifies it is recognized as done and skipped (spec: "Duplicate delivery of an already-processed event is a no-op")
- [ ] 3.5 Write a test that simulates a crashed claim (TTL expiry without completion) and verifies another worker can reclaim it (spec: "Worker crashes mid-processing")

## 4. Event processing and retry/backoff (specs/event-processing)

- [ ] 4.1 Implement the worker loop that dequeues an event, attempts the idempotency claim from Task 3.1, and only executes processing logic if the claim succeeds
- [ ] 4.2 Implement per-event `attempt` counter and exponential backoff scheduling (`base_delay * 2^attempt`, capped at `max_delay`) on processing failure, and verify unit tests assert the delay sequence matches the spec's "delay increases with attempt count" scenario
- [ ] 4.3 Implement max-attempts enforcement that moves an event to a dead-letter list instead of rescheduling once the configured max is reached, and verify a test covers "Max attempts exhausted stops retries"
- [ ] 4.4 On processing failure, release the idempotency claim (delete the claim key) before rescheduling, and verify a test confirms a retried attempt can re-claim the event ID
- [ ] 4.5 Verify a test confirms one event's backoff wait does not block other queued events from being processed (spec: "Backlogged retry does not stall the queue")
- [ ] 4.6 Implement the stub processing logic: write a success record to the event-record store on normal execution, and raise a retryable failure without writing a success record when the payload contains `"fail": true`, and verify unit tests cover both branches (spec: "Stub processing succeeds and records the event" / "Stub processing fails deliberately on request")

## 5. End-to-end verification

- [ ] 5.1 Write an end-to-end test: send the same event ID twice concurrently, and verify processing logic executes exactly once
- [ ] 5.2 Write an end-to-end test: simulate a processing failure followed by a successful retry, and verify the event is marked done exactly once and not reprocessed after success
- [ ] 5.3 Document configuration values (claim TTL, done-record TTL, base/max backoff delay, max attempts) and Redis persistence requirement (AOF) in a README or equivalent, per design.md Risks

## 6. Front-end: event visibility (specs/event-visibility)

- [ ] 6.1 Implement the event-record store updates (`status`, `attempts` per event ID in Redis) at ingestion (`status=pending`, `attempts=0`) and at each worker transition (claimed/processing, succeeded, failed/retrying, dead-lettered), and verify a test asserts the record reflects each transition
- [ ] 6.2 Implement `GET /events` returning the list of tracked events with `event_id`, `status`, and `attempts`, and verify a test covers the response shape (spec: "Listing events returns status and attempts")
- [ ] 6.3 Build a static HTML page (e.g. `static/index.html`) that fetches `GET /events` on load and renders each event's ID, status, and attempt count, and verify it loads and displays event data when served (spec: "Page displays the current event list")
- [ ] 6.4 Write an end-to-end check: send a webhook event with `"fail": true` to trigger a retry, then confirm `GET /events` and the static page reflect the increasing attempt count and updated status
