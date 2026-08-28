# Webhook Receiver with Idempotent Processing

This service solves the problem of unreliable, at-least-once webhook deliveries by ensuring incoming events are ingested quickly and processed exactly once using an idempotent, Redis-backed worker system with exponential backoff and dead-letter queueing.

## Getting Started

### Prerequisites

Ensure you have Python 3.9+ and a Redis server running locally on `localhost:6379`.

### 1. Install Dependencies

Create a virtual environment and install the package along with its development/test dependencies:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install -r requirements.txt -e .
```

### 2. Run the API

Start the FastAPI application. By default, it will listen on `0.0.0.0:8000`:

```bash
python3 -m app
```

Once running, you can access the event visibility dashboard at `http://localhost:8000/`.

### 3. Run the Worker

Start the background worker loop that processes enqueued webhooks and handles retries/backoffs:

```bash
python3 -m worker
```

### 4. Run Tests

To run the complete suite of unit, integration, and end-to-end tests:

```bash
pytest -v
```

## Architectural Decisions

The idempotency key is based on the provider-supplied ID (payload field or header) rather than a hash of the payload, because provider-supplied IDs are stable across redeliveries of the same logical event even if the body serialization or metadata change slightly. This prevents accidental deduplication failures if the provider alters formatting on redelivery, or if two genuinely different events with identical bodies are incorrectly treated as duplicates.

For the lock mechanism (claim), the system uses the atomic Redis command `SET NX EX`. This guarantees that concurrent workers racing for the same event ID cannot process it simultaneously, since only a single `SET NX` request will succeed. Using `EX` (Time-to-Live) prevents a message from being locked indefinitely if a worker suffers a crash mid-processing, allowing another worker to reclaim the event after the TTL expires.

## Configuration

The service can be configured via environment variables. The following variables are supported:

| Environment Variable | Description | Default Value |
|----------------------|-------------|---------------|
| `REDIS_HOST` | Redis server hostname | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |
| `REDIS_DB` | Redis database number | `0` |
| `REDIS_URL` | Full Redis connection URL | `redis://localhost:6379/0` |
| `QUEUE_KEY` | Redis key for the main event queue | `queue:events` |
| `DELAYED_QUEUE_KEY` | Redis key for the delayed event queue (backoff) | `queue:events:delayed` |
| `DLQ_KEY` | Redis key for the Dead Letter Queue (exhausted events) | `queue:events:dlq` |
| `EVENT_STORE_PREFIX` | Prefix for storing event status hashes | `event:` |
| `IDEMPOTENCY_PREFIX` | Prefix for storing idempotency claims | `idempotency:` |
| `CLAIM_TTL` | Time-to-Live (in seconds) for active idempotency claims | `300` (5 minutes) |
| `DONE_TTL` | Time-to-Live (in seconds) for completed event records | `604800` (7 days) |
| `BASE_DELAY` | Base backoff delay (in seconds) for the first retry attempt | `1` |
| `MAX_DELAY` | Maximum backoff delay cap (in seconds) for retries | `60` |
| `MAX_ATTEMPTS` | Maximum number of processing attempts before dead-lettering | `5` |

## Redis Persistence

To prevent data loss and guarantee the integrity of the idempotency store on server restarts, **Redis AOF (Append Only File) persistence must be enabled**. 

If Redis is running without persistence, a restart could lose active claim keys or done markers, potentially allowing a duplicate webhook redelivery to process multiple times.

### Verification

To confirm AOF is enabled on the Redis server, run the following command:

```bash
redis-cli CONFIG GET appendonly
```

It must return `yes`:

```text
1) "appendonly"
2) "yes"
```

### Configuration

To configure AOF persistence in your Redis configuration file (`redis.conf`), ensure the following lines are set:

```text
appendonly yes
appendfsync everysec
```

Using `appendfsync everysec` is the recommended balance between performance and durability.
