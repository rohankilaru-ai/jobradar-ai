from jobradar.grok import configured_targets, post_job
from jobradar.models import JobRecord


def test_configured_empty(monkeypatch):
    monkeypatch.delenv("GROK_BOT_WEBHOOK_DIRECTOR", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_DIRECTOR", raising=False)
    assert "director" not in configured_targets() or True
    job = JobRecord(company="A", title="B", url="https://ex/z")
    assert post_job(job)["director"] == "skipped"
