"""Tests for silent job refresh functionality."""

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.pipeline import refresh_jobs
from jobradar.sources import Source


def test_refresh_updates_url_and_company(tmp_path):
    """Test that refresh updates stale URL and company without notifying."""
    db = Database(tmp_path / "r.db")
    
    # Insert a job with wrong URL/company (simulating old parse bug)
    old_job = JobRecord(
        company="WrongCompany",
        title="Software Engineer Intern",
        location="SF",
        url="https://example.com/wrong",
        sources=["test-source"],
    )
    db.upsert_job(old_job)
    assert db.count_jobs() == 1
    
    # Create a mock source that returns corrected data
    correct_job = JobRecord(
        company="CorrectCompany",
        title="Software Engineer Intern",
        location="SF",
        url="https://example.com/correct",
        sources=["test-source"],
        canonical_key=old_job.canonical_key,
    )
    
    # Mock scout_all to return the corrected job
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        from jobradar.scout import ScoutResult
        return [ScoutResult(source="test-source", jobs=[correct_job], status=200)]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db, sources=[])
        
        # Verify stats
        assert stats.scanned == 1
        assert stats.matched == 1
        assert stats.rewritten == 1
        assert stats.skipped == 0
        
        # Verify the job was updated
        updated = db.get_job(old_job.canonical_key)
        assert updated is not None
        assert updated.company == "CorrectCompany"
        assert updated.url == "https://example.com/correct"
        
        # Verify no notification was sent
        assert not db.was_notified(old_job.canonical_key)
    finally:
        pipeline.scout_all = original_scout_all


def test_refresh_skips_new_jobs(tmp_path):
    """Test that refresh skips jobs not already in DB."""
    db = Database(tmp_path / "r2.db")
    
    new_job = JobRecord(
        company="NewCompany",
        title="New SWE Intern",
        location="NYC",
        url="https://example.com/new",
        sources=["test-source"],
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        from jobradar.scout import ScoutResult
        return [ScoutResult(source="test-source", jobs=[new_job], status=200)]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db, sources=[])
        
        # Should skip the new job (not in DB yet)
        assert stats.scanned == 1
        assert stats.matched == 0
        assert stats.skipped == 1
        
        # Verify job was not added to DB
        assert db.count_jobs() == 0
    finally:
        pipeline.scout_all = original_scout_all


def test_refresh_handles_closed_jobs(tmp_path):
    """Test that refresh updates closed jobs safely."""
    db = Database(tmp_path / "r3.db")
    
    closed_job = JobRecord(
        company="ClosedCo",
        title="Closed Intern",
        location="Remote",
        url="https://example.com/closed",
        sources=["test-source"],
        is_closed=True,
    )
    db.upsert_job(closed_job)
    
    # Update with new URL
    updated_job = JobRecord(
        company="ClosedCo",
        title="Closed Intern",
        location="Remote",
        url="https://example.com/closed-new",
        sources=["test-source"],
        canonical_key=closed_job.canonical_key,
        is_closed=True,
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        from jobradar.scout import ScoutResult
        return [ScoutResult(source="test-source", jobs=[updated_job], status=200)]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db, sources=[])
        
        assert stats.matched == 1
        assert stats.rewritten == 1
        
        # Verify URL was updated
        job = db.get_job(closed_job.canonical_key)
        assert job is not None
        assert job.url == "https://example.com/closed-new"
        
        # Verify no notification
        assert not db.was_notified(closed_job.canonical_key)
    finally:
        pipeline.scout_all = original_scout_all


def test_refresh_empty_sources_noop(tmp_path):
    """Test that refresh with empty sources is a no-op."""
    db = Database(tmp_path / "r4.db")
    
    # Add a job
    job = JobRecord(
        company="TestCo",
        title="Test Intern",
        location="Boston",
        url="https://example.com/test",
        sources=["test"],
    )
    db.upsert_job(job)
    
    # Refresh with empty sources
    stats = refresh_jobs(db=db, sources=[])
    
    assert stats.scanned == 0
    assert stats.matched == 0
    assert stats.rewritten == 0
    assert db.count_jobs() == 1


def test_refresh_no_change_no_rewrite(tmp_path):
    """Test that refresh skips rewriting when data is unchanged."""
    db = Database(tmp_path / "r5.db")
    
    job = JobRecord(
        company="SameCo",
        title="Same Intern",
        location="Seattle",
        url="https://example.com/same",
        sources=["test-source"],
    )
    db.upsert_job(job)
    
    # Return the exact same job data
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        from jobradar.scout import ScoutResult
        return [ScoutResult(source="test-source", jobs=[job], status=200)]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db, sources=[])
        
        # Should match but not rewrite
        assert stats.scanned == 1
        assert stats.matched == 1
        assert stats.rewritten == 0
    finally:
        pipeline.scout_all = original_scout_all


def test_refresh_source_error_handling(tmp_path):
    """Test that refresh handles source errors gracefully."""
    db = Database(tmp_path / "r6.db")
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        from jobradar.scout import ScoutResult
        return [
            ScoutResult(source="failing-source", jobs=[], error="HTTP 500"),
            ScoutResult(source="good-source", jobs=[], status=304, not_modified=True),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db, sources=[])
        
        # Should record the error
        assert len(stats.source_errors) == 1
        assert "failing-source" in stats.source_errors[0]
        assert "HTTP 500" in stats.source_errors[0]
    finally:
        pipeline.scout_all = original_scout_all
