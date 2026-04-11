"""Pipeline orchestration — IngestStage protocol + PipelineRunner."""
from __future__ import annotations

import time
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IngestStage(Protocol):
    name: str

    def run(self, ctx: Any, state: dict[str, Any]) -> dict[str, Any]: ...


class PipelineRunner:
    """Execute a list of stages sequentially, collecting metrics."""

    def __init__(self, stages: list[IngestStage]):
        self.stages = stages

    def run(self, ctx: Any, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = dict(initial_state or {})
        stages_completed = 0
        stage_durations: dict[str, float] = {}

        for stage in self.stages:
            t0 = time.monotonic()
            try:
                state = stage.run(ctx, state)
                stages_completed += 1
            except Exception as exc:
                state["error"] = str(exc)
                state["failed_stage"] = stage.name
                break
            finally:
                stage_durations[stage.name] = time.monotonic() - t0

        state["stages_completed"] = stages_completed
        state["total_stages"] = len(self.stages)
        state["stage_durations"] = stage_durations
        return state
