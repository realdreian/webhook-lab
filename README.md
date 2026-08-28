# Webhook Receiver with Idempotent Processing

A greenfield service implemented in Python using FastAPI for webhook ingestion, with Redis backing both the queue and the idempotency store, and a worker process consuming and processing enqueued events asynchronously.

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

## Infrastructure & Redis Persistence Requirements

### Redis AOF (Append Only File) Persistence

To prevent data loss and guarantee the integrity of the idempotency store on server restarts, **Redis AOF (Append Only File) persistence must be enabled**. 

If Redis is running without persistence, a restart could lose active claim keys or done markers, potentially allowing a duplicate webhook redelivery to process multiple times.

#### Verification
To confirm AOF is enabled on the Redis server, run the following command:
```bash
redis-cli CONFIG GET appendonly
```
It must return `yes`:
```text
1) "appendonly"
2) "yes"
```

To configure AOF persistence in your Redis configuration file (`redis.conf`), ensure the following lines are set:
```text
appendonly yes
appendfsync everysec
```
Using `appendfsync everysec` is the recommended balance between performance and durability.
