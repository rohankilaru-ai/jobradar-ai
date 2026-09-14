"""Director webhook tests: missing keys skip gracefully (never block fast path)."""

from unittest.mock import Mock, patch

from jobradar.db import Database
from jobradar.director import enqueue, ping_configured
from jobradar.models import JobRecord


def test_enqueue_missing_url(monkeypatch, tmp_path):
    """Missing URL skips gracefully and records skipped status."""
    monkeypatch.delenv("GROK_BOT_WEBHOOK_JOB_ANALYST", raising=False)
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "key123")
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_RESUME_MAPPER", raising=False)
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "job-analyst" not in attempted
    # Both agents record skipped when keys are missing
    assert db.count_agent_runs() == 2


def test_enqueue_missing_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "https://example.com/webhook")
    monkeypatch.delenv("GROK_BOT_KEY_RESUME_MAPPER", raising=False)
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "resume-mapper" not in attempted


def test_enqueue_empty_url(monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "key123")
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "job-analyst" not in attempted


def test_enqueue_empty_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_RESUME_MAPPER", "")
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "resume-mapper" not in attempted


def test_enqueue_whitespace_only(monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "  ")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "  ")
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "job-analyst" not in attempted


def test_enqueue_no_db_still_skips(monkeypatch):
    monkeypatch.delenv("GROK_BOT_WEBHOOK_JOB_ANALYST", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_JOB_ANALYST", raising=False)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db=None)
    assert "job-analyst" not in attempted


@patch("jobradar.director.httpx.post")
def test_enqueue_success(mock_post, monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "test-key-123")
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"runUuid": "run-abc-123"}
    mock_post.return_value = mock_response
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "job-analyst" in attempted
    assert "resume-mapper" not in attempted
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-key-123"


@patch("jobradar.director.httpx.post")
def test_enqueue_network_error(mock_post, monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "key123")
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    mock_post.side_effect = Exception("Network timeout")
    db = Database(tmp_path / "t.db")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    attempted = enqueue(job, db)
    assert "job-analyst" in attempted


def test_ping_configured_missing_keys(monkeypatch):
    monkeypatch.delenv("GROK_BOT_WEBHOOK_JOB_ANALYST", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_JOB_ANALYST", raising=False)
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_RESUME_MAPPER", raising=False)
    lines = ping_configured()
    assert len(lines) >= 2
    assert any("skipped" in line for line in lines)


def test_ping_configured_empty_keys(monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "")
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "")
    monkeypatch.setenv("GROK_BOT_KEY_RESUME_MAPPER", "")
    lines = ping_configured()
    assert all("skipped" in line for line in lines)


@patch("jobradar.director.httpx.post")
def test_ping_configured_success(mock_post, monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "test-key")
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"runUuid": "run-xyz-789"}
    mock_post.return_value = mock_response
    lines = ping_configured()
    assert any("job-analyst: ok" in line for line in lines)
    assert any("resume-mapper: skipped" in line for line in lines)


@patch("jobradar.director.httpx.post")
def test_ping_configured_partial_failure(mock_post, monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "test-key")
    monkeypatch.delenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", raising=False)
    mock_post.side_effect = Exception("Connection refused")
    lines = ping_configured()
    assert any("error" in line for line in lines)
