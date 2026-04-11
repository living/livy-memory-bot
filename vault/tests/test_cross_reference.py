"""Tests for cross-source entity matching."""
from vault.ingest.cross_reference import find_person_cross_refs


class TestCrossReference:
    def test_match_person_by_email(self):
        tldv_persons = [
            {"id": "p1", "name": "Lincoln", "email": "lincoln@livingnet.com.br"},
        ]
        trello_members = [
            {"id": "m1", "fullName": "Lincoln Quinan", "email": "lincoln@livingnet.com.br"},
        ]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert len(matches) == 1
        assert matches[0]["tldv_id"] == "p1"
        assert matches[0]["trello_id"] == "m1"

    def test_no_match_returns_empty(self):
        tldv_persons = [{"id": "p1", "name": "Bob", "email": "bob@x.com"}]
        trello_members = [{"id": "m1", "fullName": "Alice", "email": "alice@y.com"}]
        assert find_person_cross_refs(tldv_persons, trello_members) == []

    def test_match_by_normalized_name_when_no_email(self):
        tldv_persons = [{"id": "p1", "name": "Robert Urech", "email": None}]
        trello_members = [{"id": "m1", "fullName": "robert urech", "email": None}]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert len(matches) == 1

    def test_multiple_matches(self):
        tldv_persons = [
            {"id": "p1", "name": "Lincoln", "email": "lincoln@x.com"},
            {"id": "p2", "name": "Robert", "email": "robert@y.com"},
        ]
        trello_members = [
            {"id": "m1", "fullName": "Lincoln", "email": "lincoln@x.com"},
            {"id": "m2", "fullName": "Robert", "email": "robert@y.com"},
        ]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert len(matches) == 2

    def test_match_method_email_vs_name(self):
        tldv_persons = [
            {"id": "p1", "name": "Lincoln", "email": "lincoln@x.com"},
            {"id": "p2", "name": "Robert", "email": None},
        ]
        trello_members = [
            {"id": "m1", "fullName": "Lincoln Q", "email": "lincoln@x.com"},
            {"id": "m2", "fullName": "robert", "email": None},
        ]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert matches[0]["match_method"] == "email"
        assert matches[1]["match_method"] == "name"
