## Purpose

Tracks per-event status and attempt counts as events move through ingestion, processing, and retry, and exposes them for inspection via an HTTP endpoint and a minimal static HTML page.

## ADDED Requirements

### Requirement: Event status and attempt count are tracked per event ID
The system SHALL maintain, for each ingested event ID, a queryable record of its current status (e.g. pending, processing, succeeded, failed/retrying, dead-lettered) and the number of processing attempts made so far, updated as the event moves through ingestion, processing, and retry.

#### Scenario: Attempt count increments on each processing attempt
- **WHEN** a worker attempts to process an event
- **THEN** the event's recorded attempt count is incremented to reflect that attempt

#### Scenario: Status reflects the outcome of processing
- **WHEN** an event's processing attempt succeeds, fails and is scheduled for retry, or is dead-lettered after exhausting max attempts
- **THEN** the event's recorded status is updated to reflect that outcome

### Requirement: Events are listable via an HTTP endpoint
The system SHALL expose a `GET /events` endpoint that returns the list of tracked events, each including at least its event ID, current status, and attempt count.

#### Scenario: Listing events returns status and attempts
- **WHEN** a `GET /events` request is made
- **THEN** the system responds with a `2xx` status and a list of events, each including its event ID, status, and attempt count

### Requirement: A static page displays the event list
The system SHALL provide a static HTML page that, when loaded in a browser, fetches data from `GET /events` and renders the list of events including their status and attempt count.

#### Scenario: Page displays the current event list
- **WHEN** the static HTML page is loaded and `GET /events` returns a list of events
- **THEN** the page renders each event's ID, status, and attempt count
