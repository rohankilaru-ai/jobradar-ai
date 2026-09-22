"""Tests for scout health observability (overnight #33)."""

import argparse
from datetime import datetime, timezone

from jobradar.cli import cmd_health
from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.scout import ScoutResult


def test_record_scout_health_basic(tmp_path):
    """Test recording basic scout health metrics."""
    db = Database(tmp_path / "sh1.db")
    
    db.record_scout_health(
        source_name="test-source",
        status="ok",
        job_count=5,
        http_status=200,
        error_detail=None,
        was_cached=False,
    )
    
    health = db.get_scout_health_latest()
    assert len(health) == 1
    assert health[0]["source_name"] == "test-source"
    assert health[0]["status"] == "ok"
    assert health[0]["job_count"] == 5
    assert health[0]["http_status"] == 200
    assert health[0]["error_detail"] is None
    assert health[0]["was_cached"] == 0


def test_record_scout_health_error(tmp_path):
    """Test recording scout health with error."""
    db = Database(tmp_path / "sh2.db")
    
    db.record_scout_health(
        source_name="failing-source",
        status="error",
        job_count=0,
        http_status=500,
        error_detail="HTTP 500",
        was_cached=False,
    )
    
    health = db.get_scout_health_latest()
    assert len(health) == 1
    assert health[0]["status"] == "error"
    assert health[0]["http_status"] == 500
    assert health[0]["error_detail"] == "HTTP 500"


def test_record_scout_health_cached(tmp_path):
    """Test recording scout health with 304 not modified."""
    db = Database(tmp_path / "sh3.db")
    
    db.record_scout_health(
        source_name="cached-source",
        status="not_modified",
        job_count=0,
        http_status=304,
        error_detail=None,
        was_cached=True,
    )
    
    health = db.get_scout_health_latest()
    assert len(health) == 1
    assert health[0]["status"] == "not_modified"
    assert health[0]["was_cached"] == 1


def test_get_scout_health_latest_multiple_sources(tmp_path):
    """Test getting latest health for multiple sources."""
    db = Database(tmp_path / "sh4.db")
    
    # Record multiple health entries for different sources
    db.record_scout_health(
        source_name="source-a",
        status="ok",
        job_count=3,
    )
    db.record_scout_health(
        source_name="source-b",
        status="error",
        job_count=0,
        error_detail="Connection timeout",
    )
    db.record_scout_health(
        source_name="source-c",
        status="not_modified",
        job_count=0,
        was_cached=True,
    )
    
    health = db.get_scout_health_latest()
    assert len(health) == 3
    
    names = {h["source_name"] for h in health}
    assert names == {"source-a", "source-b", "source-c"}


def test_get_scout_health_latest_overwrites_old(tmp_path):
    """Test that latest health replaces old entries for same source."""
    db = Database(tmp_path / "sh5.db")
    
    # Record initial health
    db.record_scout_health(
        source_name="test-source",
        status="ok",
        job_count=5,
        fetched_at="2024-01-01T00:00:00Z",
    )
    
    # Record updated health
    db.record_scout_health(
        source_name="test-source",
        status="error",
        job_count=0,
        error_detail="HTTP 500",
        fetched_at="2024-01-01T01:00:00Z",
    )
    
    health = db.get_scout_health_latest()
    assert len(health) == 1
    assert health[0]["status"] == "error"
    assert health[0]["fetched_at"] == "2024-01-01T01:00:00Z"


def test_get_scout_health_history(tmp_path):
    """Test getting health history for a specific source."""
    db = Database(tmp_path / "sh6.db")
    
    # Record multiple entries over time
    for i in range(5):
        db.record_scout_health(
            source_name="test-source",
            status="ok" if i % 2 == 0 else "error",
            job_count=i,
            fetched_at=f"2024-01-01T{i:02d}:00:00Z",
        )
    
    history = db.get_scout_health_history("test-source", limit=10)
    assert len(history) == 5
    
    # Should be in reverse chronological order (newest first)
    assert history[0]["fetched_at"] == "2024-01-01T04:00:00Z"
    assert history[-1]["fetched_at"] == "2024-01-01T00:00:00Z"


def test_get_scout_health_history_respects_limit(tmp_path):
    """Test that health history respects limit parameter."""
    db = Database(tmp_path / "sh7.db")
    
    # Record 10 entries
    for i in range(10):
        db.record_scout_health(
            source_name="test-source",
            status="ok",
            job_count=i,
            fetched_at=f"2024-01-01T{i:02d}:00:00Z",
        )
    
    history = db.get_scout_health_history("test-source", limit=3)
    assert len(history) == 3
    
    # Should get the 3 most recent
    assert history[0]["fetched_at"] == "2024-01-01T09:00:00Z"
    assert history[2]["fetched_at"] == "2024-01-01T07:00:00Z"


def test_scout_all_records_health_metrics(tmp_path, monkeypatch):
    """Test that scout_all automatically records health metrics."""
    db = Database(tmp_path / "sh8.db")
    
    # Mock HTTP to avoid actual network calls
    import httpx
    from jobradar.scout import fetch_source
    from jobradar.sources import Source
    
    # Create a test source with aprameyak-json parser
    test_source = Source(
        name="test-source",
        kind="aprameyak-json",
        url="https://test.example.com/jobs.json"
    )
    
    # Mock the HTTP response with aprameyak-json format
    import respx
    from respx import MockRouter
    
    with respx.mock:
        respx.get(test_source.url).mock(return_value=httpx.Response(
            200,
            json=[{
                "company_name": "TestCo",
                "title": "Software Engineer Intern",
                "locations": "SF",
                "url": "https://testco.com/careers/job/12345",
                "active": True
            }],
            headers={"ETag": "test-etag"}
        ))
        
        from jobradar.scout import scout_all
        results = scout_all(db, sources=[test_source])
        
        # Verify health metrics were recorded
        health = db.get_scout_health_latest()
        assert len(health) == 1
        assert health[0]["source_name"] == "test-source"
        assert health[0]["status"] == "ok"
        assert health[0]["http_status"] == 200
        # job_count may be 0 if parser filters the job, but we're testing health recording


def test_scout_all_records_health_on_error(tmp_path):
    """Test that scout_all records health metrics when source fails."""
    db = Database(tmp_path / "sh9.db")
    
    # Mock HTTP to simulate error
    import httpx
    import respx
    from jobradar.sources import Source
    
    test_source = Source(
        name="failing-source",
        kind="json",
        url="https://fail.example.com/jobs.json"
    )
    
    with respx.mock:
        respx.get(test_source.url).mock(return_value=httpx.Response(500))
        
        from jobradar.scout import scout_all
        results = scout_all(db, sources=[test_source])
        
        # Verify error metrics were recorded
        health = db.get_scout_health_latest()
        assert len(health) == 1
        assert health[0]["source_name"] == "failing-source"
        assert health[0]["status"] == "error"
        assert health[0]["http_status"] == 500


def test_scout_all_records_health_on_304(tmp_path):
    """Test that scout_all records health metrics for 304 not modified."""
    db = Database(tmp_path / "sh10.db")
    
    # Mock HTTP to simulate 304 Not Modified
    import httpx
    import respx
    from jobradar.sources import Source
    
    test_source = Source(
        name="cached-source",
        kind="json",
        url="https://cached.example.com/jobs.json"
    )
    
    # First, seed the cache with an ETag
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO fetch_cache (url, etag, body, fetched_at) VALUES (?, ?, ?, ?)",
            (test_source.url, "old-etag", "", "2024-01-01T00:00:00Z")
        )
    
    with respx.mock:
        respx.get(test_source.url).mock(return_value=httpx.Response(304))
        
        from jobradar.scout import scout_all
        results = scout_all(db, sources=[test_source])
        
        # Verify cached metrics were recorded
        health = db.get_scout_health_latest()
        assert len(health) == 1
        assert health[0]["source_name"] == "cached-source"
        assert health[0]["status"] == "not_modified"
        assert health[0]["was_cached"] == 1


def test_health_cli_shows_scout_section_no_history(capsys, tmp_path, monkeypatch):
    """Test health CLI shows scout section with no history message."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "sh11.db"))
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "Scout health:" in output
    assert "configured sources:" in output
    assert "no history yet" in output


def test_health_cli_shows_scout_section_with_history(capsys, tmp_path, monkeypatch):
    """Test health CLI shows scout section with health metrics."""
    db_path = tmp_path / "sh12.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    
    db = Database(db_path)
    
    # Record some health metrics
    db.record_scout_health(
        source_name="source-1",
        status="ok",
        job_count=5,
    )
    db.record_scout_health(
        source_name="source-2",
        status="not_modified",
        job_count=0,
        was_cached=True,
    )
    db.record_scout_health(
        source_name="source-3",
        status="error",
        job_count=0,
        error_detail="Connection timeout",
    )
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "Scout health:" in output
    assert "last scan: ok=1 cached=1 error=1" in output
    assert "recent failures:" in output
    assert "source-3: Connection timeout" in output


def test_health_cli_shows_scout_section_all_ok(capsys, tmp_path, monkeypatch):
    """Test health CLI shows scout section when all sources are ok."""
    db_path = tmp_path / "sh13.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    
    db = Database(db_path)
    
    # Record all-ok health metrics
    db.record_scout_health(
        source_name="source-1",
        status="ok",
        job_count=3,
    )
    db.record_scout_health(
        source_name="source-2",
        status="ok",
        job_count=7,
    )
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "Scout health:" in output
    assert "last scan: ok=2 cached=0 error=0" in output
    # Should NOT show "recent failures" section when no errors
    assert "recent failures:" not in output


def test_health_cli_limits_error_display(capsys, tmp_path, monkeypatch):
    """Test health CLI shows max 5 recent errors."""
    db_path = tmp_path / "sh14.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    
    db = Database(db_path)
    
    # Record 10 error sources
    for i in range(10):
        db.record_scout_health(
            source_name=f"error-source-{i}",
            status="error",
            job_count=0,
            error_detail=f"Error {i}",
        )
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "Scout health:" in output
    assert "last scan: ok=0 cached=0 error=10" in output
    assert "recent failures:" in output
    
    # Count how many error sources are displayed
    lines = output.split("\n")
    error_lines = [l for l in lines if l.strip().startswith("error-source-")]
    
    # Should show at most 5
    assert len(error_lines) <= 5
