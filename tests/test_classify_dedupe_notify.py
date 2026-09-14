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
