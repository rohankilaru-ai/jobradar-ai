from jobradar.classify import is_priority_company, should_keep
from jobradar.db import Database
from jobradar.dedupe import is_duplicate
from jobradar.models import JobRecord
from jobradar.notify import MockNotifier, format_alert
from jobradar.pipeline import run_scan


def test_priority_and_exclude():
    assert is_priority_company("OpenAI")
    assert should_keep(JobRecord(company="X", title="Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Y", title="Nursing Intern")) is False


def test_dedupe_fuzzy():
    a = JobRecord(company="OpenAI", title="Software Engineer Intern", location="San Francisco, CA", url="")
    b = JobRecord(company="OpenAI Inc", title="Software Engineer Intern", location="San Francisco CA", url="")
    assert is_duplicate(a, b)


def test_notify_once(tmp_path):
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = MockNotifier(path=path, db=db)
    job = JobRecord(company="Stripe", title="SWE Intern", location="SF", url="https://ex/1", priority=True)
    assert n.notify(job) is True
    assert n.notify(job) is False
    text = format_alert(job)
    assert "[PRIORITY]" in text
    assert path.read_text().count("\n") == 1


def test_pipeline_empty_sources(tmp_path):
    db = Database(tmp_path / "p.db")
    stats = run_scan(db=db, sources=[])
    assert stats.fetched == 0
    assert stats.seed_mode is True
    assert stats.notified == 0


def test_pipeline_seeds_first_scan_then_alerts(tmp_path):
    from jobradar.models import JobRecord
    from jobradar.notify import MockNotifier

    db = Database(tmp_path / "s.db")
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="SF",
        url="https://example.com/stripe-intern",
        sources=["test"],
    )
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is False
    n = MockNotifier(path=tmp_path / "n.jsonl", db=db)
    assert n.notify(stored) is True
    assert n.notify(stored) is False
