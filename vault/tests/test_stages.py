"""Tests for PipelineRunner and IngestStage protocol."""
from vault.ingest.stages import PipelineRunner, IngestStage


class FakeStage:
    """A test stage that records its execution."""
    name = "fake"

    def __init__(self):
        self.called = False

    def run(self, ctx, state):
        self.called = True
        state[f"{self.name}_ran"] = True
        return state


class TestPipelineRunner:
    def test_runner_executes_stages_in_order(self):
        events = []

        class S1(IngestStage):
            name = "s1"

            def run(self, ctx, state):
                events.append("s1")
                state["a"] = 1
                return state

        class S2(IngestStage):
            name = "s2"

            def run(self, ctx, state):
                events.append("s2")
                state["b"] = 2
                return state

        runner = PipelineRunner([S1(), S2()])
        out = runner.run(ctx=None, initial_state={})
        assert events == ["s1", "s2"]
        assert out["a"] == 1 and out["b"] == 2

    def test_runner_stops_on_stage_failure(self):
        events = []

        class FailStage(IngestStage):
            name = "fail"

            def run(self, ctx, state):
                events.append("fail")
                raise RuntimeError("boom")

        class NeverReached(IngestStage):
            name = "never"

            def run(self, ctx, state):
                events.append("never")
                return state

        runner = PipelineRunner([FailStage(), NeverReached()])
        result = runner.run(ctx=None, initial_state={})
        assert "fail" in events
        assert "never" not in events
        assert result.get("error") is not None

    def test_runner_returns_stage_metrics(self):
        class Quick(IngestStage):
            name = "quick"

            def run(self, ctx, state):
                return state

        runner = PipelineRunner([Quick()])
        result = runner.run(ctx=None, initial_state={})
        assert "stages_completed" in result
        assert result["stages_completed"] == 1
