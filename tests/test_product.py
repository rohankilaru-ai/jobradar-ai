from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notion import configured as notion_on
from jobradar.notify import discord_configured, ntfy_configured, telegram_configured


def test_application_upsert(tmp_path):
    db = Database(tmp_path / "a.db")
    db.upsert_application(canonical_key="k1", company="OpenAI", title="SWE Intern", status="Seen")
    row = db.get_application("k1")
    assert row["company"] == "OpenAI"
    db.upsert_application(canonical_key="k1", status="Applied", gmail_thread_id="https://mail.google.com/x")
    row = db.get_application("k1")
    assert row["status"] == "Applied"
    assert row["gmail_thread_id"].startswith("https://")


def test_find_job_by_company(tmp_path):
    db = Database(tmp_path / "b.db")
    job = JobRecord(company="Stripe", title="SWE Intern", location="SF", url="https://ex/stripe")
    db.upsert_job(job)
    found = db.find_job_by_company("stripe.com")
    assert found is not None
    assert found.company == "Stripe"


def test_adapters_skip_without_keys(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    assert discord_configured() is False
    assert ntfy_configured() is False
    assert telegram_configured() is False
    assert notion_on() is False
