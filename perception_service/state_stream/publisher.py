import json
from typing import Dict

import redis

from shared.constants.redis_keys import user_state_key, EVENTS_STREAM


class StatePublisher:
    """Publishes perception results to Redis Streams."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)

    def publish_state(self, user_id: str, state: Dict):
        key = user_state_key(user_id)
        self.redis.set(key, json.dumps(state))

    def publish_event(self, event_type: str, payload: Dict):
        self.redis.xadd(EVENTS_STREAM, {"type": event_type, "data": json.dumps(payload)})
