from vault.research.event_key import build_event_key


def test_build_event_key_without_action_id():
    assert build_event_key("github", "pr_merged", "123") == "github:pr_merged:123"


def test_build_event_key_with_action_id():
    assert build_event_key("github", "review_submitted", "123", "a1") == "github:review_submitted:123:a1"
