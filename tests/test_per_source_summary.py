"""Tests for per-source scout summary (overnight #25)."""

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.pipeline import refresh_jobs, run_scan
from jobradar.scout import ScoutResult


def test_scan_source_summary_all_ok(tmp_path, monkeypatch):
    """Test scan shows per-source summary when all sources return OK."""
    db = Database(tmp_path / "s1.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    job1 = JobRecord(
        company="Company1",
        title="SWE Intern",
        location="SF",
        url="https://company1.com/careers/job/12345",
        sources=["source-1"],
    )
    job2 = JobRecord(
        company="Company2",
        title="ML Intern",
        location="NYC",
        url="https://company2.com/careers/job/67890",
        sources=["source-2"],
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="source-1", jobs=[job1], status=200),
            ScoutResult(source="source-2", jobs=[job2], status=200),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Check aggregate counts
        assert stats.sources_ok == 2
        assert stats.sources_not_modified == 0
        assert stats.sources_failed == 0
        
        # Check per-source details
        assert len(stats.sources) == 2
        assert stats.sources[0].name == "source-1"
        assert stats.sources[0].status == "ok"
        assert stats.sources[0].job_count == 1
        assert stats.sources[0].error_detail is None
        
        assert stats.sources[1].name == "source-2"
        assert stats.sources[1].status == "ok"
        assert stats.sources[1].job_count == 1
        assert stats.sources[1].error_detail is None
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_source_summary_mixed_statuses(tmp_path, monkeypatch):
    """Test scan shows per-source summary with mixed ok/304/error sources."""
    db = Database(tmp_path / "s2.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    job = JobRecord(
        company="GoodCo",
        title="SWE Intern",
        location="Remote",
        url="https://goodco.com/careers/job/12345",
        sources=["good-source"],
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="good-source", jobs=[job], status=200),
            ScoutResult(source="cached-source", jobs=[], status=304, not_modified=True),
            ScoutResult(source="failing-source", jobs=[], error="HTTP 500"),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Check aggregate counts
        assert stats.sources_ok == 1
        assert stats.sources_not_modified == 1
        assert stats.sources_failed == 1
        
        # Check per-source details
        assert len(stats.sources) == 3
        
        # Good source
        good = next(s for s in stats.sources if s.name == "good-source")
        assert good.status == "ok"
        assert good.job_count == 1
        assert good.error_detail is None
        
        # Cached source (304)
        cached = next(s for s in stats.sources if s.name == "cached-source")
        assert cached.status == "not_modified"
        assert cached.job_count == 0
        assert cached.error_detail is None
        
        # Failed source
        failed = next(s for s in stats.sources if s.name == "failing-source")
        assert failed.status == "error"
        assert failed.job_count == 0
        assert failed.error_detail == "HTTP 500"
        
        # Verify source_errors still populated for backwards compatibility
        assert len(stats.source_errors) == 1
        assert "failing-source" in stats.source_errors[0]
        assert "HTTP 500" in stats.source_errors[0]
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_source_summary_all_errors(tmp_path, monkeypatch):
    """Test scan shows per-source summary when all sources fail."""
    db = Database(tmp_path / "s3.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="fail-1", jobs=[], error="HTTP 404"),
            ScoutResult(source="fail-2", jobs=[], error="Connection timeout"),
            ScoutResult(source="fail-3", jobs=[], error="DNS resolution failed"),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Check aggregate counts
        assert stats.sources_ok == 0
        assert stats.sources_not_modified == 0
        assert stats.sources_failed == 3
        
        # Check per-source details
        assert len(stats.sources) == 3
        for src in stats.sources:
            assert src.status == "error"
            assert src.job_count == 0
            assert src.error_detail is not None
        
        # Verify all errors tracked
        assert len(stats.source_errors) == 3
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_source_summary_all_304(tmp_path, monkeypatch):
    """Test scan shows per-source summary when all sources return 304."""
    db = Database(tmp_path / "s4.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="cached-1", jobs=[], status=304, not_modified=True),
            ScoutResult(source="cached-2", jobs=[], status=304, not_modified=True),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Check aggregate counts
        assert stats.sources_ok == 0
        assert stats.sources_not_modified == 2
        assert stats.sources_failed == 0
        
        # Check per-source details
        assert len(stats.sources) == 2
        for src in stats.sources:
            assert src.status == "not_modified"
            assert src.job_count == 0
            assert src.error_detail is None
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_preserves_soft_fail_behavior(tmp_path, monkeypatch):
    """Test that one bad source doesn't abort the rest (soft-fail preserved)."""
    db = Database(tmp_path / "s5.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    job1 = JobRecord(
        company="BeforeFail",
        title="SWE Intern",
        location="SF",
        url="https://beforefail.com/careers/job/12345",
        sources=["before-fail"],
    )
    job2 = JobRecord(
        company="AfterFail",
        title="ML Intern",
        location="NYC",
        url="https://afterfail.com/careers/job/67890",
        sources=["after-fail"],
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="before-fail", jobs=[job1], status=200),
            ScoutResult(source="failing", jobs=[], error="Network error"),
            ScoutResult(source="after-fail", jobs=[job2], status=200),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Verify both good sources processed successfully
        assert stats.sources_ok == 2
        assert stats.sources_failed == 1
        assert stats.new == 2
        
        # Verify jobs from both good sources are in DB
        assert db.count_jobs() == 2
        job1_stored = db.get_job(job1.canonical_key)
        job2_stored = db.get_job(job2.canonical_key)
        assert job1_stored is not None
        assert job2_stored is not None
    finally:
        pipeline.scout_all = original_scout_all


def test_refresh_source_summary_mixed_statuses(tmp_path, monkeypatch):
    """Test refresh shows per-source summary with mixed statuses."""
    db = Database(tmp_path / "r1.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    # Pre-populate DB with an existing job
    existing = JobRecord(
        company="ExistingCo",
        title="Existing Intern",
        location="Remote",
        url="https://existingco.com/careers/job/12345",
        sources=["good-source"],
    )
    db.upsert_job(existing)
    
    # Updated version of the existing job
    updated = JobRecord(
        company="ExistingCo",
        title="Existing Intern",
        location="Remote",
        url="https://existingco.com/careers/job/12345-updated",
        sources=["good-source"],
        canonical_key=existing.canonical_key,
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="good-source", jobs=[updated], status=200),
            ScoutResult(source="cached-source", jobs=[], status=304, not_modified=True),
            ScoutResult(source="failing-source", jobs=[], error="HTTP 503"),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = refresh_jobs(db=db)
        
        # Check aggregate counts
        assert stats.sources_ok == 1
        assert stats.sources_not_modified == 1
        assert stats.sources_failed == 1
        
        # Check per-source details
        assert len(stats.sources) == 3
        
        # Good source with 1 matched job
        good = next(s for s in stats.sources if s.name == "good-source")
        assert good.status == "ok"
        assert good.job_count == 1
        
        # Cached source
        cached = next(s for s in stats.sources if s.name == "cached-source")
        assert cached.status == "not_modified"
        assert cached.job_count == 0
        
        # Failed source
        failed = next(s for s in stats.sources if s.name == "failing-source")
        assert failed.status == "error"
        assert failed.job_count == 0
        assert failed.error_detail == "HTTP 503"
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_source_count_reflects_kept_jobs(tmp_path, monkeypatch):
    """Test that source job_count reflects kept jobs (after classification), not raw fetched."""
    db = Database(tmp_path / "s6.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    # One good job that passes classification
    good_job = JobRecord(
        company="TechCo",
        title="Software Engineer Intern",
        location="SF",
        url="https://techco.com/careers/job/12345",
        sources=["test-source"],
    )
    
    # One bad job that won't pass classification (nursing intern)
    bad_job = JobRecord(
        company="Hospital",
        title="Nursing Intern",
        location="Boston",
        url="https://hospital.com/careers/job/67890",
        sources=["test-source"],
    )
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="test-source", jobs=[good_job, bad_job], status=200),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Should have fetched 2 but kept only 1
        assert stats.fetched == 2
        assert stats.kept == 1
        
        # Source summary should show 1 job (kept count, not fetched)
        assert len(stats.sources) == 1
        assert stats.sources[0].job_count == 1
        assert stats.sources[0].status == "ok"
    finally:
        pipeline.scout_all = original_scout_all


def test_scan_empty_source_shows_zero_jobs(tmp_path, monkeypatch):
    """Test that a source returning no jobs shows job_count=0 with status=ok."""
    db = Database(tmp_path / "s7.db")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    from jobradar import pipeline
    original_scout_all = pipeline.scout_all
    
    def mock_scout_all(db, sources=None):
        return [
            ScoutResult(source="empty-source", jobs=[], status=200),
        ]
    
    pipeline.scout_all = mock_scout_all
    
    try:
        stats = run_scan(db=db, alert_all=True)
        
        # Should succeed but with 0 jobs
        assert stats.sources_ok == 1
        assert len(stats.sources) == 1
        assert stats.sources[0].name == "empty-source"
        assert stats.sources[0].status == "ok"
        assert stats.sources[0].job_count == 0
    finally:
        pipeline.scout_all = original_scout_all
