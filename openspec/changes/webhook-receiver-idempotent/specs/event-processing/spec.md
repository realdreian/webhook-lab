## Purpose

Consumes queued webhook events and executes their processing logic, retrying failures with exponential backoff up to a bounded number of attempts before routing the event to a dead-letter state.

## ADDED Requirements

### Requirement: Queued events are processed asynchronously
The system SHALL consume events from the queue independently of the HTTP ingestion path and SHALL execute each event's processing logic exactly once per delivery attempt.

#### Scenario: Event is picked up and processed
- **WHEN** an event is present on the queue and a worker is available
- **THEN** the worker dequeues the event and executes its processing logic

### Requirement: Failed processing is retried with exponential backoff
When an event's processing attempt fails with a retryable error, the system SHALL reschedule that event for a later attempt after a delay that increases exponentially with the number of prior attempts, up to a configured maximum number of attempts.

#### Scenario: First failure is retried after a short delay
- **WHEN** an event's processing attempt fails for the first time
- **THEN** the system reschedules the event for a retry after the configured base backoff delay

#### Scenario: Repeated failures increase the delay
- **WHEN** an event has already failed and been retried `n` times and fails again
- **THEN** the system reschedules the next retry after a delay that is larger than the delay used for attempt `n`, following the configured exponential backoff curve

#### Scenario: Max attempts exhausted stops retries
- **WHEN** an event has failed processing on its configured maximum number of attempts
- **THEN** the system stops retrying that event and marks it as permanently failed (dead-lettered) instead of rescheduling it again

### Requirement: A single failing event does not block other events
The system SHALL continue processing other queued events while a given event is waiting for its next retry attempt or has been dead-lettered.

#### Scenario: Backlogged retry does not stall the queue
- **WHEN** one event is waiting out its backoff delay before its next retry
- **THEN** other unrelated events on the queue continue to be dequeued and processed
