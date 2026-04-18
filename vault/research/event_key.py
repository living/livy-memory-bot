def build_event_key(source: str, event_type: str, object_id: str, action_id: str | None = None) -> str:
    if action_id is None:
        return f"{source}:{event_type}:{object_id}"
    return f"{source}:{event_type}:{object_id}:{action_id}"
