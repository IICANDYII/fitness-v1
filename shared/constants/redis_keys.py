def user_state_key(user_id: str) -> str:
    return f"state:user:{user_id}"


EVENTS_STREAM = "events:fitness"
