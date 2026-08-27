## Purpose

Accepts incoming webhook events over HTTP POST, validates that each event carries a usable unique identifier, and enqueues valid events for asynchronous processing without doing any processing work synchronously.

## ADDED Requirements

### Requirement: Webhook events are accepted via HTTP POST
The system SHALL expose an HTTP endpoint that accepts `POST` requests carrying a webhook event payload and SHALL respond without performing the event's business processing synchronously.

#### Scenario: Valid event is accepted
- **WHEN** a `POST` request with a valid JSON payload and a usable event ID is received
- **THEN** the system enqueues the event for processing and responds with a `2xx` status before processing completes

#### Scenario: Malformed payload is rejected
- **WHEN** a `POST` request body is not valid JSON or does not match the expected webhook schema
- **THEN** the system responds with a `400` status and does not enqueue anything

### Requirement: Event ID is required for ingestion
The system SHALL derive a unique event ID for each incoming request from a provider-supplied field (payload field or HTTP header) and SHALL reject any request for which no such ID can be determined.

#### Scenario: Request without a usable event ID is rejected
- **WHEN** a `POST` request arrives with no recognizable event ID in its payload or headers
- **THEN** the system responds with a `400` status and does not enqueue the request

#### Scenario: Event ID is extracted and attached to the queued event
- **WHEN** a `POST` request arrives with a valid event ID
- **THEN** the system associates that exact event ID with the enqueued event so downstream processing can deduplicate on it

### Requirement: Ingestion responds quickly regardless of downstream load
The system SHALL acknowledge a valid incoming webhook request as soon as it is durably enqueued, independent of how long processing or retries for that event later take.

#### Scenario: Queue accepts event under processing backlog
- **WHEN** a valid webhook request arrives while previously queued events are still being processed or retried
- **THEN** the system still enqueues the new event and responds with a `2xx` status without waiting for the backlog to clear
