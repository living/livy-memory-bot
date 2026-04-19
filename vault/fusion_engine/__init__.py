"""Fusion engine public API."""

from vault.fusion_engine.confidence import compute_confidence
from vault.fusion_engine.contradiction import Contradiction, detect_contradiction
from vault.fusion_engine.engine import FusionResult, fuse
from vault.fusion_engine.supersession import apply_supersession, should_supersede

__all__ = [
    "compute_confidence",
    "Contradiction",
    "detect_contradiction",
    "FusionResult",
    "fuse",
    "apply_supersession",
    "should_supersede",
]
