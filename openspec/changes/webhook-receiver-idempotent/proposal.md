## Why

We need a webhook receiver that ingests events over HTTP POST, queues them for asynchronous processing, and retries failed processing with exponential backoff. Webhook providers commonly redeliver the same event (timeouts, retries on their side, at-least-once delivery guarantees), and our own retry/backoff loop can also re-attempt an event that actually succeeded but failed to ack in time. Without idempotency, either path causes the same event to be processed more than once, which is unacceptable for anything with side effects (charging a customer, sending a notification, mutating state). Idempotency is the central correctness requirement this system is built around, not an add-on.

## What Changes

- New FastAPI HTTP endpoint that accepts `POST` webhook requests, validates the payload, and enqueues the event without doing synchronous processing work.
- New Redis-backed queue that holds pending events and feeds a worker process.
- New worker/consumer that processes queued events and, on failure, reschedules the event with exponential backoff up to a configurable max attempt count.
- New idempotency guarantee: each event is uniquely identified by an ID supplied by the webhook provider (payload field or header, e.g. `event_id` / `X-Webhook-Id`); a request or a retry for an event ID that has already completed processing is a no-op, and concurrent workers cannot both process the same event ID at once.
- Requests missing a usable provider event ID are rejected at ingestion (`400`) rather than silently accepted, since they cannot be deduplicated.
- Processing logic for this change is an explicit stub: it writes a record of the processed event and deliberately raises a retryable failure when the payload contains `"fail": true`, so retry/backoff and idempotency behavior can be exercised end-to-end without real business logic.
- New `GET /events` endpoint and a static HTML page that lists tracked events with their status and attempt count, for basic operator visibility into what the receiver is doing.

## Capabilities

### New Capabilities
- `webhook-ingestion`: Accepting, validating, and enqueueing incoming webhook POST requests.
- `event-processing`: Consuming queued events and executing retry with exponential backoff on failure, using a stub processing implementation.
- `event-idempotency`: Guaranteeing each provider event ID is processed at most once, including under concurrent workers and redeliveries.
- `event-visibility`: Tracking per-event status and attempt counts, and exposing them via a `GET /events` endpoint and a static HTML page.

## Impact

- New Python service (FastAPI app + worker process) and a Redis dependency (queue, idempotency store, and event-status records).
- New API surface: `POST /webhooks/{provider}` (public ingestion endpoint) and `GET /events` (event status/attempts listing).
- New static asset: a minimal HTML page served alongside the API that consumes `GET /events`.
- Deployment impact: introduces Redis as required infrastructure; worker process must run alongside the API process.
- Local dev: Redis is already installed and running locally (with AOF enabled) for this change — no docker-compose or install step is needed.
