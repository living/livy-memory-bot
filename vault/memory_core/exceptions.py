class MemoryCoreError(Exception):
    """Base exception for all memory core errors."""

    pass


class CorruptStateError(MemoryCoreError):
    """Raised when an invariant is violated during write.

    This exception is NOT strippable with -O (unlike assert).
    """

    pass


class DuplicateClaimError(MemoryCoreError):
    """Raised when attempting to insert a duplicate claim."""

    pass


class MissingEvidenceError(MemoryCoreError):
    """Raised when claim has no evidence_ids or evidence_ids is empty."""

    pass
