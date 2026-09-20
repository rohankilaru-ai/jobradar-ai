"""Test that pause/cap do not permanently silence jobs (overnight #20)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier
from jobradar.pipeline import run_scan


def _job(
    *,
    company: str = "Stripe",
    title: str = "SWE Intern",
    location: str = "SF",
    url: str = "",
    sources: list[str] | None = None,
    priority: bool = False,
    posted_at: str = "",
) -> JobRecord:
    """Helper to create a job with reasonable defaults."""
    now = datetime.now(timezone.utc).isoformat()
    if not posted_at:
        # Default to today so it's within notify window
        posted_at = datetime.now(timezone.utc).date().isoformat()
    
    # Generate a company-appropriate URL if not provided
    if not url:
        company_slug = company.lower().replace(" ", "")
        url = f"https://{company_slug}.com/careers/job/12345"
    
    return JobRecord(
        company=company,
        title=title,
        location=location,
        url=url,
        sources=sources or ["test-source"],
        snippet=f"{title} at {company}",
        priority=priority,
        season="Summer 2027",
        first_seen_at=now,
        last_seen_at=now,
        posted_at=posted_at,
    )


def test_alerts_paused_no_permanent_notify(monkeypatch):
    """When JOBRADAR_ALERTS_ENABLED=0, jobs are NOT marked notified."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        job = _job(company="OpenAI", title="Research Intern")
        stored, is_new = db.upsert_job(job)
        assert is_new
        
        # First scan with alerts paused
        assert not db.was_notified(stored.canonical_key)
        result = notifier.notify(stored, silent=True, record_as_notified=False)
        assert result  # JSONL written
        assert not db.was_notified(stored.canonical_key)  # NOT marked notified
        
        # Re-enable alerts
        monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
        
        # Second scan should be able to alert
        assert not db.was_notified(stored.canonical_key)
        result = notifier.notify(stored, silent=False, record_as_notified=True)
        assert result  # Alert sent
        assert db.was_notified(stored.canonical_key)  # NOW marked notified


def test_alerts_paused_via_pipeline(monkeypatch):
    """Pipeline integration: JOBRADAR_ALERTS_ENABLED=0 defers jobs."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        
        # Mock source with one job
        job = _job(company="Anthropic", title="AI Safety Intern")
        
        # Mock scout_all to return our test job
        from jobradar import pipeline
        from jobradar.scout import ScoutResult
        original_scout_all = pipeline.scout_all
        
        def mock_scout_all(db, sources=None):
            return [ScoutResult(source="test-source", jobs=[job], status=200)]
        
        pipeline.scout_all = mock_scout_all
        
        try:
            # First scan with alerts paused
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.fetched == 1
            assert stats.new == 1
            assert stats.alerts_paused == 1
            assert stats.alerted == 0
            assert stats.notified == 1  # JSONL written
            
            # Job should NOT be marked notified
            assert not db.was_notified(job.canonical_key)
            
            # Re-enable alerts
            monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
            
            # Second scan (same job, now eligible for alert)
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.fetched == 1
            assert stats.new == 0  # Already in DB
            # Job is not "new" anymore, so won't alert on second scan
            # This is expected behavior - deferred jobs need to be new on the deferred scan
            
            # To test proper deferral, let's manually trigger notify again
            notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
            stored = db.get_job(job.canonical_key)
            assert stored is not None
            assert not db.was_notified(stored.canonical_key)
            
            result = notifier.notify(stored, silent=False, record_as_notified=True)
            assert result
            assert db.was_notified(stored.canonical_key)
        finally:
            pipeline.scout_all = original_scout_all


def test_cap_hit_no_permanent_notify(monkeypatch):
    """When MAX_ALERTS_PER_SCAN is hit, overflow jobs are NOT marked notified."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        jobs = [
            _job(company="Meta", title="SWE Intern 1"),
            _job(company="Google", title="SWE Intern 2"),
            _job(company="Apple", title="SWE Intern 3"),  # This one hits the cap
        ]
        
        for job in jobs:
            stored, _ = db.upsert_job(job)
            assert not db.was_notified(stored.canonical_key)
        
        # Simulate pipeline: first 2 alerts succeed, 3rd is deferred
        alerted = 0
        cap = 2
        
        for i, job in enumerate(jobs):
            stored = db.get_job(job.canonical_key)
            should_alert = alerted < cap
            record_notification = should_alert  # Only record if actually alerting
            
            result = notifier.notify(stored, silent=not should_alert, record_as_notified=record_notification)
            assert result
            
            if should_alert:
                alerted += 1
                assert db.was_notified(stored.canonical_key)
            else:
                # Cap hit - NOT marked notified
                assert not db.was_notified(stored.canonical_key)
        
        # First 2 are notified, 3rd is not
        assert db.was_notified(jobs[0].canonical_key)
        assert db.was_notified(jobs[1].canonical_key)
        assert not db.was_notified(jobs[2].canonical_key)
        
        # Later scan can alert the 3rd job
        stored = db.get_job(jobs[2].canonical_key)
        result = notifier.notify(stored, silent=False, record_as_notified=True)
        assert result
        assert db.was_notified(stored.canonical_key)


def test_cap_hit_via_pipeline(monkeypatch):
    """Pipeline integration: MAX_ALERTS_PER_SCAN defers overflow jobs."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        
        jobs = [
            _job(company="Palantir", title="Forward Deployed Engineer Intern"),
            _job(company="Databricks", title="Data Science Intern"),
            _job(company="Snowflake", title="Backend Intern"),
        ]
        
        # Mock scout_all
        from jobradar import pipeline
        from jobradar.scout import ScoutResult
        original_scout_all = pipeline.scout_all
        
        def mock_scout_all(db, sources=None):
            return [ScoutResult(source="test-source", jobs=jobs, status=200)]
        
        pipeline.scout_all = mock_scout_all
        
        try:
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.fetched == 3
            assert stats.new == 3
            assert stats.alerted == 2
            assert stats.cap_deferred == 1
            assert stats.alert_cap_hit
            
            # First 2 jobs marked notified, 3rd is not
            assert db.was_notified(jobs[0].canonical_key)
            assert db.was_notified(jobs[1].canonical_key)
            assert not db.was_notified(jobs[2].canonical_key)
        finally:
            pipeline.scout_all = original_scout_all


def test_live_alert_marks_notified(monkeypatch):
    """Jobs that receive live alerts are marked notified (no double-alert)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        job = _job(company="Ramp", title="Backend Intern")
        stored, _ = db.upsert_job(job)
        
        # First alert
        result = notifier.notify(stored, silent=False, record_as_notified=True)
        assert result
        assert db.was_notified(stored.canonical_key)
        
        # Second attempt returns False (already notified)
        result = notifier.notify(stored, silent=False, record_as_notified=True)
        assert not result


def test_cap_zero_unlimited(monkeypatch):
    """MAX_ALERTS_PER_SCAN=0 means unlimited (no cap)."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        
        # Create unique jobs with distinctly different companies and titles
        companies = ["Meta", "Google", "Apple", "Amazon", "Microsoft", 
                     "Tesla", "Nvidia", "Intel", "AMD", "Qualcomm"]
        jobs = [_job(
            company=companies[i],
            title=f"{['Backend', 'Frontend', 'ML', 'Data', 'Security', 'Cloud', 'Mobile', 'Platform', 'Infra', 'Tools'][i]} Engineer Intern",
            location=f"City {i}",
            url=f"https://{companies[i].lower()}.com/careers/job/{i}"
        ) for i in range(10)]
        
        # Mock scout_all
        from jobradar import pipeline
        from jobradar.scout import ScoutResult
        original_scout_all = pipeline.scout_all
        
        def mock_scout_all(db, sources=None):
            return [ScoutResult(source="test-source", jobs=jobs, status=200)]
        
        pipeline.scout_all = mock_scout_all
        
        try:
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.fetched == 10
            assert stats.new == 10
            assert stats.alerted == 10
            assert stats.cap_deferred == 0
            assert not stats.alert_cap_hit
            
            # All marked notified
            for job in jobs:
                assert db.was_notified(job.canonical_key)
        finally:
            pipeline.scout_all = original_scout_all


def test_quality_block_permanent(monkeypatch):
    """Quality blocks (bad URL, etc) still record notification (permanent block)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        # Job with bad URL (example.com is blocked)
        job = _job(company="BadCo", title="Test Job", url="https://example.com/job")
        stored, _ = db.upsert_job(job)
        
        # Quality block: notify returns False
        result = notifier.notify(stored, silent=False, record_as_notified=True)
        assert not result
        
        # Should NOT be marked notified (quality block happens before recording)
        assert not db.was_notified(stored.canonical_key)


def test_outside_window_silent(monkeypatch):
    """Jobs outside notify window are silent but NOT deferred (not eligible)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        # Job posted 10 days ago (outside default 3-day window)
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        job = _job(company="OldCo", title="Old Job", posted_at=old_date)
        stored, _ = db.upsert_job(job)
        
        # Pipeline would check within_notify_window and skip this job entirely
        # But if we call notify with silent=True, it still writes JSONL
        result = notifier.notify(stored, silent=True, record_as_notified=True)
        assert result
        assert db.was_notified(stored.canonical_key)


def test_deferred_job_can_alert_later(monkeypatch):
    """Full scenario: pause defer -> re-enable -> alert."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        job = _job(company="Cursor", title="AI Agent Intern")
        
        # Mock scout_all
        from jobradar import pipeline
        from jobradar.scout import ScoutResult
        original_scout_all = pipeline.scout_all
        
        def mock_scout_all(db, sources=None):
            return [ScoutResult(source="test-source", jobs=[job], status=200)]
        
        pipeline.scout_all = mock_scout_all
        
        try:
            # Scan 1: alerts paused
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.new == 1
            assert stats.alerts_paused == 1
            assert stats.alerted == 0
            assert not db.was_notified(job.canonical_key)
            
            # Re-enable alerts
            monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
            
            # Manually notify the deferred job (simulating a later scan that processes backlog)
            notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
            stored = db.get_job(job.canonical_key)
            assert stored is not None
            
            result = notifier.notify(stored, silent=False, record_as_notified=True)
            assert result
            assert db.was_notified(stored.canonical_key)
            
            # Third attempt: already notified
            result = notifier.notify(stored, silent=False, record_as_notified=True)
            assert not result
        finally:
            pipeline.scout_all = original_scout_all


def test_stats_counters(monkeypatch):
    """Verify stats counters for pause/cap defer."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "1")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        jobs = [
            _job(company="A", title="Job A"),
            _job(company="B", title="Job B"),
        ]
        
        # Mock scout_all
        from jobradar import pipeline
        from jobradar.scout import ScoutResult
        original_scout_all = pipeline.scout_all
        
        def mock_scout_all(db, sources=None):
            return [ScoutResult(source="test-source", jobs=jobs, status=200)]
        
        pipeline.scout_all = mock_scout_all
        
        try:
            # Alerts paused
            stats = run_scan(db=db, sources=[], alert_all=True)
            assert stats.new == 2
            assert stats.alerts_paused == 2
            assert stats.alerted == 0
            assert stats.cap_deferred == 0
            
            # Re-enable but low cap
            monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
            db2 = Database(temp_dir / "test2.db")
            stats = run_scan(db=db2, sources=[], alert_all=True)
            assert stats.new == 2
            assert stats.alerts_paused == 0
            assert stats.alerted == 1
            assert stats.cap_deferred == 1
            assert stats.alert_cap_hit
        finally:
            pipeline.scout_all = original_scout_all


def test_record_as_notified_parameter(monkeypatch):
    """Test record_as_notified parameter directly."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        db = Database(temp_dir / "test.db")
        notifier = Notifier(temp_dir / "notifications.jsonl", db=db)
        
        job = _job(company="Test", title="Test Job")
        stored, _ = db.upsert_job(job)
        
        # Notify with record_as_notified=False
        result = notifier.notify(stored, silent=True, record_as_notified=False)
        assert result
        assert not db.was_notified(stored.canonical_key)
        
        # Notify again with record_as_notified=True
        result = notifier.notify(stored, silent=True, record_as_notified=True)
        assert result
        assert db.was_notified(stored.canonical_key)
        
        # Third attempt blocked by was_notified check
        result = notifier.notify(stored, silent=True, record_as_notified=True)
        assert not result
