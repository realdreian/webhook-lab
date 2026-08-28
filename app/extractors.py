from typing import Any, Mapping

PROVIDER_ID_HEADERS: dict[str, list[str]] = {
    "github": ["x-github-delivery", "x-webhook-id", "x-event-id"],
    "stripe": ["x-webhook-id", "x-event-id"],
}

PROVIDER_ID_FIELDS: dict[str, list[str]] = {
    "github": ["id", "delivery_id", "event_id"],
    "stripe": ["id", "event_id"],
}

DEFAULT_ID_HEADERS = ["x-webhook-id", "x-event-id", "x-delivery-id", "webhook-id"]
DEFAULT_ID_FIELDS = ["event_id", "id", "eventId", "delivery_id"]

def extract_event_id(provider: str, payload: Any, headers: Mapping[str, str]) -> str | None:
    """Extract event ID from request headers or payload based on provider configuration or defaults."""
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    # 1. Check provider-specific or default headers
    header_keys = PROVIDER_ID_HEADERS.get(provider.lower(), []) + DEFAULT_ID_HEADERS
    for h in header_keys:
        if h in headers_lower and headers_lower[h].strip():
            return headers_lower[h].strip()
            
    # 2. Check payload fields
    if isinstance(payload, dict):
        field_keys = PROVIDER_ID_FIELDS.get(provider.lower(), []) + DEFAULT_ID_FIELDS
        for f in field_keys:
            val = payload.get(f)
            if val is not None and str(val).strip():
                return str(val).strip()

    return None
