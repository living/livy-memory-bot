"""Tests for Trello event_key collision-safe strategy in pipeline.py."""
from __future__ import annotations

import hashlib

import pytest

from vault.research.pipeline import build_trello_event_key


def _hash16(s: str) -> str:
    """Compute first 16 hex chars of SHA256 of a string."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


class TestTrelloEventKeyUsesActionIdWhenPresent:
    """event_key should use action_id when present and non-empty."""

    def test_action_id_used_for_card_created(self):
        """action_id takes priority for card_created events."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": "action_abc123",
            "card_id": "card_xyz",
            "list_id": "list_456",
            "timestamp": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "action_abc123"

    def test_action_id_used_for_card_updated(self):
        """action_id takes priority for card_updated events."""
        event = {
            "source": "trello",
            "event_type": "trello:card_updated",
            "action_id": "action_def456",
            "card_id": "card_xyz",
            "list_id": "list_456",
            "timestamp": "2026-04-18T11:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "action_def456"

    def test_action_id_used_for_list_moved(self):
        """action_id takes priority for list_moved events."""
        event = {
            "source": "trello",
            "event_type": "trello:list_moved",
            "action_id": "action_ghi789",
            "card_id": "card_xyz",
            "target_list_id": "list_dest",
            "timestamp": "2026-04-18T12:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "action_ghi789"

    def test_action_id_used_for_member_added(self):
        """action_id takes priority for member_added events."""
        event = {
            "source": "trello",
            "event_type": "trello:member_added",
            "action_id": "action_member_add",
            "member_id": "member_123",
            "timestamp": "2026-04-18T13:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "action_member_add"

    def test_action_id_used_for_member_removed(self):
        """action_id takes priority for member_removed events."""
        event = {
            "source": "trello",
            "event_type": "trello:member_removed",
            "action_id": "action_member_rem",
            "member_id": "member_456",
            "timestamp": "2026-04-18T14:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "action_member_rem"

    def test_empty_action_id_treated_as_missing(self):
        """Empty string action_id should fall through to next strategy."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": "",
            "card_id": "card_xyz",
            "list_id": "list_456",
            "timestamp": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Should fall through to list_id + updated_at_ts
        assert key == "list_456_1776506400"

    def test_whitespace_action_id_treated_as_missing(self):
        """Whitespace-only action_id should be treated as missing."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": "   ",
            "card_id": "card_xyz",
            "list_id": "list_456",
            "timestamp": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Should fall through to list_id + updated_at_ts
        assert key == "list_456_1776506400"


class TestTrelloEventKeyFallbackListIdUpdatedAt:
    """Fallback for card_created/card_updated: list_id_at_event + updated_at_ts."""

    def test_card_created_fallback(self):
        """card_created without action_id uses list_id + updated_at_ts."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": None,
            "card_id": "card_xyz",
            "list_id": "list_todo",
            "timestamp": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "list_todo_1776506400"

    def test_card_updated_fallback(self):
        """card_updated without action_id uses list_id + updated_at_ts."""
        event = {
            "source": "trello",
            "event_type": "trello:card_updated",
            "action_id": None,
            "card_id": "card_xyz",
            "list_id": "list_doing",
            "timestamp": "2026-04-18T11:30:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "list_doing_1776511800"

    def test_timestamp_converted_to_unix_epoch(self):
        """Timestamp must be converted to Unix epoch seconds."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": None,
            "list_id": "list_abc",
            "timestamp": "2026-04-18T00:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # 2026-04-18T00:00:00.000Z = 1776470400
        assert key == "list_abc_1776470400"


class TestTrelloEventKeyFallbackListMoved:
    """Fallback for list_moved: target_list_id + card_id + timestamp."""

    def test_list_moved_with_target_list_id_and_card_id(self):
        """list_moved uses target_list_id + card_id + timestamp when all present."""
        event = {
            "source": "trello",
            "event_type": "trello:list_moved",
            "action_id": None,
            "card_id": "card_abc",
            "target_list_id": "list_dest",
            "timestamp": "2026-04-18T12:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "list_dest_card_abc_1776513600"

    def test_list_moved_without_card_id(self):
        """list_moved falls through to exact hash fallback when card_id is missing."""
        event = {
            "source": "trello",
            "event_type": "trello:list_moved",
            "action_id": None,
            "list_id": "list_abc",
            "target_list_id": "list_dest",
            "timestamp": "2026-04-18T12:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Hash input uses field1=list_id, field2=card_id (missing => ""), timestamp
        assert key == _hash16("list_abc__2026-04-18T12:00:00.000Z")

    def test_list_moved_without_target_list_id(self):
        """list_moved falls back to hash when target_list_id missing."""
        event = {
            "source": "trello",
            "event_type": "trello:list_moved",
            "action_id": None,
            "card_id": "card_xyz",
            "timestamp": "2026-04-18T12:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Should use hash fallback
        assert len(key) == 16


class TestTrelloEventKeyFallbackMemberAddedRemoved:
    """Fallback for member_added/member_removed: member_id + timestamp."""

    def test_member_added_fallback(self):
        """member_added without action_id uses member_id + timestamp."""
        event = {
            "source": "trello",
            "event_type": "trello:member_added",
            "action_id": None,
            "member_id": "member_john",
            "timestamp": "2026-04-18T13:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "member_john_1776517200"

    def test_member_removed_fallback(self):
        """member_removed without action_id uses member_id + timestamp."""
        event = {
            "source": "trello",
            "event_type": "trello:member_removed",
            "action_id": None,
            "member_id": "member_jane",
            "timestamp": "2026-04-18T14:30:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "member_jane_1776522600"


class TestTrelloEventKeyFallbackHashDeterministic:
    """Hash fallback for ambiguous events: hash16(field1 + '_' + field2 + '_' + timestamp)."""

    def test_hash_fallback_is_deterministic(self):
        """Same event must produce same key across multiple calls."""
        event = {
            "source": "trello",
            "event_type": "trello:unknown_type",
            "action_id": None,
            "timestamp": "2026-04-18T15:00:00.000Z",
        }
        key1 = build_trello_event_key(event)
        key2 = build_trello_event_key(event)
        assert key1 == key2

    def test_hash_fallback_produces_16_char_hex(self):
        """Hash fallback must produce exactly 16 hex characters."""
        event = {
            "source": "trello",
            "event_type": "trello:unknown_type",
            "action_id": None,
            "timestamp": "2026-04-18T15:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_hash_fallback_different_for_different_events(self):
        """Different events should produce different hashes."""
        event1 = {
            "source": "trello",
            "event_type": "trello:unknown_type",
            "action_id": None,
            "field1": "alpha",
            "timestamp": "2026-04-18T15:00:00.000Z",
        }
        event2 = {
            "source": "trello",
            "event_type": "trello:unknown_type",
            "action_id": None,
            "field1": "beta",
            "timestamp": "2026-04-18T15:00:00.000Z",
        }
        key1 = build_trello_event_key(event1)
        key2 = build_trello_event_key(event2)
        assert key1 != key2

    def test_hash_uses_field1_field2_timestamp(self):
        """Hash fallback must use field1 + '_' + field2 + '_' + timestamp format."""
        event = {
            "source": "trello",
            "event_type": "trello:unknown_type",
            "action_id": None,
            "field1": "alpha",
            "field2": "beta",
            "timestamp": "2026-04-18T16:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Key should be hash16 of "alpha_beta_2026-04-18T16:00:00.000Z"
        expected_input = "alpha_beta_2026-04-18T16:00:00.000Z"
        expected_hash = _hash16(expected_input)
        assert key == expected_hash

    def test_card_created_without_list_id_uses_hash_fallback(self):
        """card_created without list_id must fall through to hash fallback."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": None,
            "card_id": "card_xyz",
            # no list_id
            "timestamp": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Should fall through to hash
        assert len(key) == 16

    def test_member_event_without_member_id_uses_hash_fallback(self):
        """member_added without member_id must fall through to hash fallback."""
        event = {
            "source": "trello",
            "event_type": "trello:member_added",
            "action_id": None,
            # no member_id
            "timestamp": "2026-04-18T13:00:00.000Z",
        }
        key = build_trello_event_key(event)
        # Should fall through to hash
        assert len(key) == 16

    def test_missing_timestamp_none_falls_back_to_hash(self):
        """timestamp=None should be handled gracefully with deterministic hash fallback."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": None,
            "list_id": "list_todo",
            "card_id": "card_xyz",
            "timestamp": None,
        }
        key = build_trello_event_key(event)
        assert key == _hash16("list_todo_card_xyz_")

    def test_invalid_timestamp_falls_back_to_hash(self):
        """Invalid timestamp string should be handled gracefully with hash fallback."""
        event = {
            "source": "trello",
            "event_type": "trello:card_updated",
            "action_id": None,
            "list_id": "list_doing",
            "card_id": "card_xyz",
            "timestamp": "invalid-string",
        }
        key = build_trello_event_key(event)
        assert key == _hash16("list_doing_card_xyz_invalid-string")

    def test_date_field_used_when_timestamp_absent(self):
        """date field should be used as timestamp fallback when timestamp is absent."""
        event = {
            "source": "trello",
            "event_type": "trello:card_created",
            "action_id": None,
            "list_id": "list_todo",
            "date": "2026-04-18T10:00:00.000Z",
        }
        key = build_trello_event_key(event)
        assert key == "list_todo_1776506400"
