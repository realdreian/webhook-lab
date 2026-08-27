## Purpose

Guarantees that each webhook event, identified by its provider-supplied event ID, has its processing logic executed at most once — regardless of provider redeliveries, internal retries, or concurrent workers.

## ADDED Requirements

### Requirement: Each event ID is processed at most once
The system SHALL ensure that the processing logic for a given event ID runs to successful completion at most one time, even if the event is delivered or enqueued multiple times.

#### Scenario: Duplicate delivery of an already-processed event is a no-op
- **WHEN** a webhook event with an event ID that has already completed processing successfully is received again
- **THEN** the system does not re-execute the processing logic for that event ID and treats the request as already handled

#### Scenario: Retry of an event that already succeeded is a no-op
- **WHEN** an internal retry attempt is scheduled for an event ID whose processing already completed successfully (e.g. success was recorded but acknowledgment was lost)
- **THEN** the system skips re-executing the processing logic for that attempt

### Requirement: Concurrent workers cannot both process the same event ID
The system SHALL ensure that, when multiple workers are running, at most one worker executes the processing logic for a given event ID at any given time.

#### Scenario: Two workers race on the same event ID
- **WHEN** two workers simultaneously attempt to claim the same event ID for processing
- **THEN** exactly one worker proceeds to execute the processing logic and the other worker skips or defers that event ID

### Requirement: Idempotency state survives worker restarts and crashes
The system SHALL persist the record of which event IDs have completed processing (or are currently claimed for processing) in durable storage that outlives an individual worker process, so that a worker restart does not cause a completed or in-flight event to be reprocessed from scratch as if new.

#### Scenario: Worker crashes after completing processing but before acknowledging the queue
- **WHEN** a worker successfully completes processing an event, crashes before removing it from the queue, and the event is redelivered
- **THEN** the redelivered event is recognized as already completed and is not reprocessed

#### Scenario: Worker crashes mid-processing
- **WHEN** a worker crashes while holding a claim on an event ID that has not yet completed processing
- **THEN** the system eventually allows another worker to reclaim and process that event ID (the claim does not block the event forever)

### Requirement: Idempotency check is scoped to the provider event ID
The system SHALL key idempotency state on the unique event ID extracted at ingestion and SHALL treat two requests with the same event ID as the same event regardless of differences in transport-level details (timestamp of delivery, request headers unrelated to identity, etc.).

#### Scenario: Same event ID, different delivery metadata, still deduplicated
- **WHEN** the same event ID is redelivered with a different delivery timestamp or unrelated header values
- **THEN** the system still recognizes it as a duplicate of the original event and does not process it again
