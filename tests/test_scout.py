"""Tests for scout retry logic on transient HTTP failures."""

from unittest.mock import Mock, patch

import httpx
import pytest

from jobradar.db import Database
from jobradar.scout import ScoutResult, _is_transient_error, fetch_source, scout_all
from jobradar.sources import Source


def test_is_transient_error_429():
    """HTTP 429 (rate limit) is transient."""
    assert _is_transient_error(None, 429) is True


def test_is_transient_error_5xx():
    """HTTP 5xx errors are transient."""
    assert _is_transient_error(None, 500) is True
    assert _is_transient_error(None, 502) is True
    assert _is_transient_error(None, 503) is True
    assert _is_transient_error(None, 504) is True


def test_is_transient_error_404():
    """HTTP 404 is a hard failure (not transient)."""
    assert _is_transient_error(None, 404) is False


def test_is_transient_error_4xx_except_429():
    """HTTP 4xx (except 429) are hard failures."""
    assert _is_transient_error(None, 400) is False
    assert _is_transient_error(None, 401) is False
    assert _is_transient_error(None, 403) is False
    assert _is_transient_error(None, 410) is False


def test_is_transient_error_timeout():
    """httpx timeout is transient."""
    exc = httpx.TimeoutException("timeout")
    assert _is_transient_error(exc, None) is True


def test_is_transient_error_connect():
    """httpx connection errors are transient."""
    exc = httpx.ConnectError("connect failed")
    assert _is_transient_error(exc, None) is True
    
    exc = httpx.ConnectTimeout("connect timeout")
    assert _is_transient_error(exc, None) is True


def test_is_transient_error_other_exception():
    """Other exceptions are not transient (handled elsewhere)."""
    exc = ValueError("bad value")
    assert _is_transient_error(exc, None) is False


def test_fetch_source_success_after_500_retry(tmp_path):
    """Transient 500 on first attempt, success on retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    # Mock HTTP client: first call returns 500, second call returns 200
    mock_response_500 = Mock()
    mock_response_500.status_code = 500
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.text = '[]'  # Empty job list
    mock_response_200.headers = {}
    
    mock_client = Mock()
    mock_client.get.side_effect = [mock_response_500, mock_response_200]
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is None
    assert result.status == 200
    assert result.jobs == []
    assert mock_client.get.call_count == 2  # Initial + retry


def test_fetch_source_success_after_429_retry(tmp_path):
    """Transient 429 on first attempt, success on retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.text = '[]'
    mock_response_200.headers = {}
    
    mock_client = Mock()
    mock_client.get.side_effect = [mock_response_429, mock_response_200]
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is None
    assert result.status == 200
    assert mock_client.get.call_count == 2


def test_fetch_source_success_after_timeout_retry(tmp_path):
    """Transient timeout on first attempt, success on retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.text = '[]'
    mock_response_200.headers = {}
    
    mock_client = Mock()
    mock_client.get.side_effect = [
        httpx.TimeoutException("timeout"),
        mock_response_200
    ]
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is None
    assert result.status == 200
    assert mock_client.get.call_count == 2


def test_fetch_source_success_after_connect_error_retry(tmp_path):
    """Transient connection error on first attempt, success on retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.text = '[]'
    mock_response_200.headers = {}
    
    mock_client = Mock()
    mock_client.get.side_effect = [
        httpx.ConnectError("connection failed"),
        mock_response_200
    ]
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is None
    assert result.status == 200
    assert mock_client.get.call_count == 2


def test_fetch_source_no_retry_on_404(tmp_path):
    """Hard failure (404) should not retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_404 = Mock()
    mock_response_404.status_code = 404
    
    mock_client = Mock()
    mock_client.get.return_value = mock_response_404
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error == "HTTP 404"
    assert result.status == 404
    assert mock_client.get.call_count == 1  # No retry


def test_fetch_source_no_retry_on_403(tmp_path):
    """Hard failure (403) should not retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_403 = Mock()
    mock_response_403.status_code = 403
    
    mock_client = Mock()
    mock_client.get.return_value = mock_response_403
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error == "HTTP 403"
    assert result.status == 403
    assert mock_client.get.call_count == 1  # No retry


def test_fetch_source_two_500_failures(tmp_path):
    """Two consecutive 500 failures return error result."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_500 = Mock()
    mock_response_500.status_code = 500
    
    mock_client = Mock()
    mock_client.get.return_value = mock_response_500
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error == "HTTP 500"
    assert result.status == 500
    assert mock_client.get.call_count == 2  # Initial + one retry


def test_fetch_source_two_timeout_failures(tmp_path):
    """Two consecutive timeout failures return error result."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_client = Mock()
    mock_client.get.side_effect = [
        httpx.TimeoutException("timeout 1"),
        httpx.TimeoutException("timeout 2")
    ]
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is not None
    assert "timeout" in result.error.lower() or "TimeoutException" in result.error
    assert result.status is None
    assert mock_client.get.call_count == 2


def test_fetch_source_304_still_works(tmp_path):
    """HTTP 304 (not modified) works correctly with ETag."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    # Store an ETag in cache first
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO fetch_cache (url, etag, body, fetched_at) VALUES (?, ?, ?, ?)",
            (source.url, '"etag123"', '', '2024-01-01T00:00:00Z')
        )
    
    mock_response_304 = Mock()
    mock_response_304.status_code = 304
    
    mock_client = Mock()
    mock_client.get.return_value = mock_response_304
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.not_modified is True
    assert result.status == 304
    assert result.jobs == []
    assert result.error is None
    assert mock_client.get.call_count == 1


def test_scout_all_one_source_fails_others_succeed(tmp_path):
    """Soft-fail of one source does not abort other sources."""
    db = Database(tmp_path / "test.db")
    
    source1 = Source(name="source-1", url="https://example.com/jobs1.json", kind="aprameyak")
    source2 = Source(name="source-2", url="https://example.com/jobs2.json", kind="aprameyak")
    source3 = Source(name="source-3", url="https://example.com/jobs3.json", kind="aprameyak")
    
    # Mock responses: source1 fails with 404, source2 succeeds, source3 succeeds
    mock_response_404 = Mock()
    mock_response_404.status_code = 404
    
    mock_response_200_s2 = Mock()
    mock_response_200_s2.status_code = 200
    mock_response_200_s2.text = '[]'
    mock_response_200_s2.headers = {}
    
    mock_response_200_s3 = Mock()
    mock_response_200_s3.status_code = 200
    mock_response_200_s3.text = '[]'
    mock_response_200_s3.headers = {}
    
    with patch('jobradar.scout.httpx.Client') as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = [
            mock_response_404,  # source1 fails
            mock_response_200_s2,  # source2 succeeds
            mock_response_200_s3,  # source3 succeeds
        ]
        
        results = scout_all(db, sources=[source1, source2, source3])
    
    assert len(results) == 3
    assert results[0].source == "source-1"
    assert results[0].error == "HTTP 404"
    assert results[1].source == "source-2"
    assert results[1].error is None
    assert results[2].source == "source-3"
    assert results[2].error is None


def test_scout_all_transient_failure_retries_per_source(tmp_path):
    """Each source with transient failure gets its own retry."""
    db = Database(tmp_path / "test.db")
    
    source1 = Source(name="source-1", url="https://example.com/jobs1.json", kind="aprameyak")
    source2 = Source(name="source-2", url="https://example.com/jobs2.json", kind="aprameyak")
    
    mock_response_500 = Mock()
    mock_response_500.status_code = 500
    
    mock_response_200_s1 = Mock()
    mock_response_200_s1.status_code = 200
    mock_response_200_s1.text = '[]'
    mock_response_200_s1.headers = {}
    
    mock_response_200_s2 = Mock()
    mock_response_200_s2.status_code = 200
    mock_response_200_s2.text = '[]'
    mock_response_200_s2.headers = {}
    
    with patch('jobradar.scout.httpx.Client') as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = [
            mock_response_500,  # source1 first attempt fails
            mock_response_200_s1,  # source1 retry succeeds
            mock_response_500,  # source2 first attempt fails
            mock_response_200_s2,  # source2 retry succeeds
        ]
        
        results = scout_all(db, sources=[source1, source2])
    
    assert len(results) == 2
    assert results[0].source == "source-1"
    assert results[0].error is None
    assert results[1].source == "source-2"
    assert results[1].error is None
    assert mock_client.get.call_count == 4  # 2 sources × 2 attempts each


def test_fetch_source_200_success_no_retry(tmp_path):
    """Successful 200 response on first attempt does not retry."""
    db = Database(tmp_path / "test.db")
    source = Source(name="test-source", url="https://example.com/jobs.json", kind="aprameyak")
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.text = '[]'
    mock_response_200.headers = {"ETag": '"abc123"'}
    
    mock_client = Mock()
    mock_client.get.return_value = mock_response_200
    
    result = fetch_source(source, db, client=mock_client)
    
    assert result.error is None
    assert result.status == 200
    assert result.jobs == []
    assert mock_client.get.call_count == 1  # No retry on success
