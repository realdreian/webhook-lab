## Context

See proposal.md - Why. This is a greenfield service: a FastAPI process handles ingestion, Redis backs both the queue and the idempotency store, and a separate worker process (or pool) consumes the queue. Requirements are in `specs/webhook-ingestion`, `specs/event-processing`, and `specs/event-idempotency`.

## Goals / Non-Goals

**Goals:**
- Make double-processing of the same provider event ID structurally hard to do by accident, not just documented as a rule.
- Keep the ingestion path (`POST` handler) fast and free of processing logic — it only validates and enqueues.
- Make retry/backoff and idempotency composable: a retried attempt goes through the same dedup check as a fresh delivery.

- Give an operator basic visibility into event status and attempt counts (via `GET /events` and a static page) without building a full admin UI.

**Non-Goals:**
- Exactly-once delivery guarantees at the transport level (webhook providers are at-least-once; we only guarantee at-most-once *processing*, not at-most-once *receipt*).
- Ordering guarantees across different event IDs.
- Multi-tenant provider abstraction beyond extracting an ID field/header per request — no per-provider plugin system in this change.
- Real business processing logic: this change ships a stub (see below); a full-featured admin dashboard, auth-gated UI, or real-time (websocket/polling) updates for the events page — a static page that fetches once on load is sufficient for this change.

## Decisions

### Idempotency key: provider-supplied event ID
Use the ID the webhook provider sends (a payload field such as `event_id`, or a header such as `X-Webhook-Id`) as the idempotency key, rather than hashing the payload.

- **Why**: Provider IDs are stable across redeliveries of the *same* logical event even if the payload serialization differs slightly (field ordering, added metadata). Payload hashing would treat two genuinely different events with identical bodies as duplicates, and would treat the same event as "different" if the provider mutates the payload slightly on redelivery.
- **Alternative considered**: Hash of the payload. Rejected as the default because it conflates "same bytes" with "same event." Kept as a documented rejection path: if no provider ID is found, ingestion returns `400` rather than silently falling back to a hash (a provider integration that needs hash-based dedup can be added later as an explicit, documented exception per-provider, not a silent default).

### Idempotency store: Redis, `SET NX EX` as an atomic claim
A worker claims an event ID by attempting `SET idempotency:{event_id} claimed NX EX <ttl>`. Only the worker whose `SET NX` succeeds proceeds to process; others skip. On successful completion, the key is overwritten to `SET idempotency:{event_id} done EX <retention>` (longer TTL). On failure, the key is deleted so a retry can re-claim.

- **Why**: `SET NX` is atomic in Redis, so two workers racing on the same event ID cannot both succeed — this directly satisfies "concurrent workers cannot both process the same event ID." Using the same store for the claim and the completion record means one lookup tells a worker whether an event ID is unclaimed, claimed-in-progress, or done.
- **Why a TTL on the claim**: if a worker crashes mid-processing, the claim key expires and another worker can eventually reclaim the event ID, satisfying "claim does not block the event forever." The TTL must be set longer than the expected worst-case processing time for one attempt.
- **Alternative considered**: A relational table with a `UNIQUE` constraint on event ID and a status column, updated via `INSERT ... ON CONFLICT`. This is also viable and arguably more durable than Redis, but the proposal's chosen stack is Redis for both queue and idempotency store, keeping infrastructure to one moving part; this is recorded as a real alternative in case Redis's durability guarantees (AOF/RDB persistence) prove insufficient later.
- **Risk this decision accepts**: Redis persistence must be enabled (AOF recommended) or a Redis restart could lose idempotency state for events completed since the last snapshot, allowing a stale redelivery to reprocess. This is called out under Risks below.

### Queue + retry: Redis-based delayed queue, per-event attempt counter
Use a Redis structure that supports scheduling a re-delivery at a future time (e.g. a sorted set keyed by "ready at" timestamp, or an equivalent Redis Streams + delayed-retry pattern) rather than relying on external message-broker-native retry features. Each queued event carries an `attempt` counter. On failure, the worker computes `delay = base_delay * 2^attempt` (capped at a max delay) and re-inserts the event with `attempt + 1` scheduled for `now + delay`. When `attempt` reaches the configured max, the event is moved to a dead-letter list instead of being rescheduled.

- **Why**: Keeps retry/backoff logic in application code where it can be tested directly against the spec's scenarios (first failure retried, delay grows, max attempts exhausted stops retries), rather than depending on broker-specific retry semantics that vary in how they expose attempt count and delay.
- **Alternative considered**: A managed queue with native retry/DLQ support (e.g. SQS). Rejected for this change per the proposal's chosen stack (FastAPI + Redis); may be revisited if operational scale demands it.

### Processing and idempotency-claim ordering
A worker claims the event ID (via `SET NX`) *before* executing processing logic, and only marks it `done` *after* processing logic completes successfully. If processing fails, the claim key is deleted before the retry is scheduled, so the next attempt can re-claim.

- **Why**: Claiming before executing (rather than checking-then-executing non-atomically) is what makes the concurrent-worker guarantee hold; checking "has this been done?" as a separate read followed by a separate write would leave a race window between the two.

### Processing logic: stub with a deliberate-failure trigger
The processing logic invoked by the worker (Decision above) is, for this change, a stub: it writes a record of the event (event ID, outcome) to the event-record store and returns success — unless the event payload contains `"fail": true`, in which case it raises a retryable error instead of writing a success record.

- **Why**: A payload-triggered failure lets retry/backoff and idempotency behavior be exercised deterministically end-to-end (including over the real HTTP path, for manual and e2e testing) without wiring real business logic in this change. It replaces "process the event" with the minimum behavior needed to prove the surrounding guarantees work.
- **Alternative considered**: Only exercising failure paths via mocking/patching in unit tests. Rejected because it would leave no way to trigger a real retry/idempotency cycle through the actual API for manual verification or e2e tests (see tasks.md 5.1/5.2 and 6.4).

### Event-record store for status/attempts (`event-visibility`)
Reuse Redis for the event-record store: one hash per event ID (e.g. `event:{event_id}` with fields `status`, `attempts`), written by the worker at each transition (claimed, succeeded, failed/rescheduled, dead-lettered) and by the ingestion handler on initial enqueue (`status=pending`, `attempts=0`). `GET /events` reads this store.

- **Why**: Keeps infrastructure to the one moving part already chosen (Redis) instead of adding a second database just for status reporting; the fields needed (`status`, `attempts`) are exactly what the worker already tracks for retry/backoff (Decision above).
- **Alternative considered**: A separate SQL table for event records. Rejected for the same reason the idempotency store stayed on Redis rather than SQL — one less moving part, revisit if reporting needs grow beyond a simple list.

### Local dev Redis: use the existing local instance directly
Redis is already installed and running locally (`localhost:6379`) with AOF persistence enabled. The app connects to it directly via configuration; this change does not add docker-compose or any Redis install/provisioning step.

- **Why**: The infrastructure precondition this design already required (Redis with AOF, see Risks below) is met locally; adding docker-compose here would be redundant setup work outside this change's scope.

## Risks / Trade-offs

- **[Risk] Redis data loss on restart** → could cause a completed event's `done` marker to be lost, allowing reprocessing on redelivery. **Mitigation**: require Redis persistence (AOF, `appendfsync everysec` or stricter) in deployment; local dev already has AOF enabled (verified in task 1.3), but this must also be verified in any other environment this is deployed to.
- **[Risk] Claim TTL shorter than actual processing time** → a slow processing attempt could have its claim expire while still running, letting a second worker start processing concurrently. **Mitigation**: set claim TTL well above p99 processing latency, and treat this as a tunable that should be revisited if processing logic changes.
- **[Risk] Provider sends an event ID that is reused for logically different events** → would cause the system to incorrectly treat a new event as a duplicate. **Mitigation**: out of our control; document that this system trusts the provider's event ID to be unique per logical event, per the "Non-Goals" above.
- **[Trade-off] No payload-hash fallback for providers without an event ID** → those integrations are rejected at ingestion (`400`) instead of accepted with weaker dedup guarantees. This is intentional: silently accepting undeduplicable events would violate the core idempotency requirement.

## Migration Plan

Greenfield service — no existing data or traffic to migrate. Initial deployment: stand up Redis (with persistence enabled), deploy the FastAPI ingestion app, deploy the worker process(es), verify with a smoke test that sends the same event ID twice and confirms single processing.

## Open Questions

- Exact max attempt count and base/max backoff delay values are left as configuration (not hardcoded) — defaults should be chosen during implementation and can be tuned later without changing specs or approach.
- Dead-letter events: this change defines that they stop retrying and are marked permanently failed, but does not specify an operator-facing replay/inspection mechanism. Can be added in a follow-up change without affecting these specs.
