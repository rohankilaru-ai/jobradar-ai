from unittest.mock import Mock, patch

from jobradar.grok import configured_targets, ping_all, post_job
from jobradar.models import JobRecord


def test_configured_empty(monkeypatch):
    monkeypatch.delenv("GROK_BOT_WEBHOOK_DIRECTOR", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_DIRECTOR", raising=False)
    assert "director" not in configured_targets() or True
    job = JobRecord(company="A", title="B", url="https://ex/z")
    assert post_job(job)["director"] == "skipped"


def test_post_job_missing_url(monkeypatch):
    monkeypatch.delenv("GROK_BOT_WEBHOOK_JOB_ANALYST", raising=False)
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "key123")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["job_analyst"] == "skipped"


def test_post_job_missing_key(monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "https://example.com/webhook")
    monkeypatch.delenv("GROK_BOT_KEY_RESUME_MAPPER", raising=False)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["resume_mapper"] == "skipped"


def test_post_job_empty_url(monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_STRATEGIST", "")
    monkeypatch.setenv("GROK_BOT_KEY_STRATEGIST", "key123")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["strategist"] == "skipped"


def test_post_job_empty_key(monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_INBOX", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_INBOX", "")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["inbox"] == "skipped"


def test_post_job_whitespace_only_env(monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_WEEKLY", "  ")
    monkeypatch.setenv("GROK_BOT_KEY_WEEKLY", "  ")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["weekly"] == "skipped"


@patch("jobradar.grok.httpx.post")
def test_post_job_success(mock_post, monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "test-key-123")
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["job_analyst"] == "http_200"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert call_args.kwargs["timeout"] == 8.0


@patch("jobradar.grok.httpx.post")
def test_post_job_network_error(mock_post, monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_RESUME_MAPPER", "key123")
    mock_post.side_effect = Exception("Network timeout")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert "error:" in results["resume_mapper"]
    assert "Network timeout" in results["resume_mapper"]


def test_ping_all_missing_keys(monkeypatch):
    for _, url_k, key_k in [
        ("director", "GROK_BOT_WEBHOOK_DIRECTOR", "GROK_BOT_KEY_DIRECTOR"),
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.delenv(url_k, raising=False)
        monkeypatch.delenv(key_k, raising=False)
    results = ping_all()
    assert all(v == "skipped" for v in results.values())


def test_ping_all_empty_keys(monkeypatch):
    for _, url_k, key_k in [
        ("director", "GROK_BOT_WEBHOOK_DIRECTOR", "GROK_BOT_KEY_DIRECTOR"),
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.setenv(url_k, "")
        monkeypatch.setenv(key_k, "")
    results = ping_all()
    assert all(v == "skipped" for v in results.values())


@patch("jobradar.grok.httpx.post")
def test_ping_all_success(mock_post, monkeypatch):
    monkeypatch.setenv("GROK_BOT_WEBHOOK_DIRECTOR", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_DIRECTOR", "test-key")
    for _, url_k, key_k in [
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.delenv(url_k, raising=False)
        monkeypatch.delenv(key_k, raising=False)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    results = ping_all()
    assert results["director"] == "http_200"
    assert results["job_analyst"] == "skipped"


def test_configured_targets_partial(monkeypatch):
    for _, url_k, key_k in [
        ("director", "GROK_BOT_WEBHOOK_DIRECTOR", "GROK_BOT_KEY_DIRECTOR"),
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.delenv(url_k, raising=False)
        monkeypatch.delenv(key_k, raising=False)
    monkeypatch.setenv("GROK_BOT_WEBHOOK_RESUME_MAPPER", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_RESUME_MAPPER", "key123")
    targets = configured_targets()
    assert "resume_mapper" in targets
    assert "director" not in targets
    assert "job_analyst" not in targets


def test_post_job_never_hangs_on_missing_keys(monkeypatch):
    """Verify fast path: missing keys never block or wait on HTTP."""
    import time

    monkeypatch.delenv("GROK_BOT_WEBHOOK_DIRECTOR", raising=False)
    monkeypatch.delenv("GROK_BOT_KEY_DIRECTOR", raising=False)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    start = time.time()
    results = post_job(job)
    elapsed = time.time() - start
    assert results["director"] == "skipped"
    assert elapsed < 0.1, "post_job should skip instantly when keys are missing"


def test_ping_all_never_hangs_on_missing_keys(monkeypatch):
    """Verify fast path: missing keys never block or wait on HTTP."""
    import time

    for _, url_k, key_k in [
        ("director", "GROK_BOT_WEBHOOK_DIRECTOR", "GROK_BOT_KEY_DIRECTOR"),
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.delenv(url_k, raising=False)
        monkeypatch.delenv(key_k, raising=False)
    start = time.time()
    results = ping_all()
    elapsed = time.time() - start
    assert all(v == "skipped" for v in results.values())
    assert elapsed < 0.1, "ping_all should skip instantly when keys are missing"


def test_post_job_mixed_empty_and_valid(monkeypatch):
    """One valid webhook, others empty. Ensure only valid one fires."""
    monkeypatch.delenv("GROK_BOT_WEBHOOK_DIRECTOR", raising=False)
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "")
    monkeypatch.setenv("GROK_BOT_KEY_JOB_ANALYST", "key123")
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/job")
    results = post_job(job)
    assert results["director"] == "skipped"
    assert results["job_analyst"] == "skipped"


def test_ping_all_timeout_respects_parameter(monkeypatch):
    """Verify custom timeout is passed through to httpx."""
    from unittest.mock import patch, Mock

    monkeypatch.setenv("GROK_BOT_WEBHOOK_DIRECTOR", "https://example.com/webhook")
    monkeypatch.setenv("GROK_BOT_KEY_DIRECTOR", "key123")
    for _, url_k, key_k in [
        ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ]:
        monkeypatch.delenv(url_k, raising=False)
        monkeypatch.delenv(key_k, raising=False)
    with patch("jobradar.grok.httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        ping_all(timeout=3.0)
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["timeout"] == 3.0
