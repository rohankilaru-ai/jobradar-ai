from jobradar.db import Database
from jobradar.models import JobRecord


def test_upsert_unique_canonical_key(tmp_path):
    db = Database(tmp_path / "t.db")
    job = JobRecord(
        company="OpenAI",
        title="SWE Intern",
        location="SF",
        url="https://example.com/a",
        sources=["src-a"],
    )
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    assert db.count_jobs() == 1

    again = JobRecord(
        company="OpenAI",
        title="SWE Intern",
        location="San Francisco",
        url="https://example.com/a",
        sources=["src-b"],
        snippet="hello",
        priority=True,
    )
    merged, is_new2 = db.upsert_job(again)
    assert is_new2 is False
    assert db.count_jobs() == 1
    assert set(merged.sources) == {"src-a", "src-b"}
    assert merged.priority is True
    assert merged.snippet == "hello"


def test_notification_once(tmp_path):
    db = Database(tmp_path / "t.db")
    key = "url:abc"
    assert db.was_notified(key) is False
    db.record_notification(key, "mock", "hi", "2026-01-01T00:00:00Z")
    assert db.was_notified(key) is True
