#!/usr/bin/env python3
"""
signal_bus.py — Unified signal event bus with JSONL persistence.
"""
import uuid, json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class SignalEvent(BaseModel):
    """Normalized signal event across all sources."""
    # Identity
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))  # set by bus.start_cycle()
    # Provenance
    source: str  # "tldv" | "logs" | "github" | "feedback"
    priority: int = Field(ge=1, le=4)
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: Optional[str] = None
    # Content
    topic_ref: Optional[str] = None
    signal_type: str  # "decision" | "topic_mentioned" | "success" | "failure" | "correction"
    payload: dict = Field(default_factory=dict)  # description, evidence, confidence
    # Origin
    origin_id: str
    origin_url: Optional[str] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        return data


class SignalBus:
    """
    In-memory event bus for SignalEvents.
    Provides correlation_id tracking, topic-based filtering, and JSONL persistence.
    """

    def __init__(self):
        self.events: list[SignalEvent] = []
        self.correlation_id: Optional[str] = None

    def start_cycle(self) -> str:
        """Start a new curation cycle. Returns correlation_id."""
        self.correlation_id = str(uuid.uuid4())
        return self.correlation_id

    def emit(self, event: SignalEvent) -> SignalEvent:
        """Emit an event with the current correlation_id."""
        if self.correlation_id is None:
            self.start_cycle()
        event.correlation_id = self.correlation_id
        self.events.append(event)
        return event

    def get_by_topic(self, topic_ref: str) -> list[SignalEvent]:
        return [e for e in self.events if e.topic_ref == topic_ref]

    def get_by_source(self, source: str) -> list[SignalEvent]:
        return [e for e in self.events if e.source == source]

    def get_signals_for_topic(self, topic_ref: str) -> list[SignalEvent]:
        """Alias for get_by_topic for semantic clarity in analyzers."""
        return self.get_by_topic(topic_ref)

    def persist(self, path: Path, mode: str = "write") -> None:
        """Write all events as JSON Lines."""
        path.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if mode == "append" else "w"
        with path.open(file_mode) as f:
            for e in self.events:
                f.write(e.model_dump_json() + "\n")

    def load(self, path: Path) -> None:
        """Load events from JSON Lines file."""
        self.events = []
        if not path.exists():
            return
        with path.open("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.events.append(SignalEvent.model_validate_json(line))