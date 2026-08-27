## Why

We need a webhook receiver that ingests events over HTTP POST, queues them for asynchronous processing, and retries failed processing with exponential backoff. Webhook providers commonly redeliver the same event (timeouts, retries on their side, at-least-once delivery guarantees), and our own retry/backoff loop can also re-attempt an event that actually succeeded but failed to ack in time. Without idempotency, either path causes the same event to be processed more than once, which is unacceptable for anything with side effects (charging a customer, sending a notification, mutating state). Idempotency is the central correctness requirement this system is built around, not an add-on.

## What Changes

- New FastAPI HTTP endpoint that accepts `POST` webhook requests, validates the payload, and enqueues the event without doing synchronous processing work.
- New Redis-backed queue that holds pending events and feeds a worker process.
- New worker/consumer that processes queued events and, on failure, reschedules the event with exponential backoff up to a configurable max attempt count.
- New idempotency guarantee: each event is uniquely identified by an ID supplied by the webhook provider (payload field or header, e.g. `event_id` / `X-Webhook-Id`); a request or a retry for an event ID that has already completed processing is a no-op, and concurrent workers cannot both process the same event ID at once.
- Requests missing a usable provider event ID are rejected at ingestion (`400`) rather than silently accepted, since they cannot be deduplicated.

## Capabilities

### New Capabilities
- `webhook-ingestion`: Accepting, validating, and enqueueing incoming webhook POST requests.
- `event-processing`: Consuming queued events and executing retry with exponential backoff on failure.
- `event-idempotency`: Guaranteeing each provider event ID is processed at most once, including under concurrent workers and redeliveries.

## Impact

- New Python service (FastAPI app + worker process) and a Redis dependency (queue + idempotency store).
- New API surface: `POST /webhooks/{provider}` (or similar) as the public ingestion endpoint.
- Deployment impact: introduces Redis as required infrastructure; worker process must run alongside the API process.
