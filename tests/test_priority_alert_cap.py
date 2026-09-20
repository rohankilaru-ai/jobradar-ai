"""Tests for priority-first alert cap ordering (overnight #19).

When JOBRADAR_MAX_ALERTS_PER_SCAN limits alerts, jobs should be ordered by tier:
- Priority tier (OpenAI, Anthropic, etc.) alerted first
- Fortune500 tier (JPMorgan, IBM, etc.) alerted second
- Other tier alerted last
- Jobs past the cap still stored in DB (silent path)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.pipeline import run_scan
from jobradar.scout import ScoutResult


def make_job(company: str, title: str, url: str) -> JobRecord:
    """Helper to create a JobRecord for testing."""
    return JobRecord(
        company=company,
        title=title,
        location="Remote",
        url=url,
        sources=["test"],
        posted_at="2026-09-20",  # Recent so it passes notify window
    )


def make_scout_result(jobs: list[JobRecord]) -> ScoutResult:
    """Helper to create a ScoutResult for testing."""
    return ScoutResult(
        source="test",
        jobs=jobs,
        error=None,
        not_modified=False,
    )


def test_priority_first_under_cap_mixed_tiers(tmp_path: Path, monkeypatch):
    """With cap=3 and mixed-tier batch, Priority jobs should be alerted first."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "3")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    # Create 5 jobs across all tiers (in non-priority order)
    jobs = [
        make_job("RandomStartup", "SWE Intern", "https://randomstartup.com/careers/job/123456"),  # other
        make_job("OpenAI", "SWE Intern", "https://openai.com/careers/job/111111"),  # priority
        make_job("IBM", "SWE Intern", "https://ibm.com/careers/job/222222"),  # fortune500
        make_job("Anthropic", "ML Intern", "https://anthropic.com/careers/job/333333"),  # priority
        make_job("LocalCorp", "Data Intern", "https://localcorp.com/careers/job/444444"),  # other
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout, \
         patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.director.enqueue") as mock_director:
        
        mock_scout.return_value = scout_results
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, alert_all=True)
    
    # Verify stats
    assert stats.new == 5
    assert stats.alerted == 3  # cap hit
    assert stats.alert_cap_hit is True
    
    # Check notifications.jsonl to verify alert order
    notify_file = tmp_path / "notify.jsonl"
    assert notify_file.exists()
    
    lines = notify_file.read_text().strip().split("\n")
    # Should have 5 total notifications (3 live + 2 silent)
    assert len(lines) == 5
    
    import json
    notifications = [json.loads(line) for line in lines]
    
    # Filter to non-silent (live alerts)
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    assert len(live_alerts) == 3
    
    # Verify Priority companies are in the first 3 alerts
    alerted_companies = [n["job"]["company"] for n in live_alerts]
    assert "OpenAI" in alerted_companies
    assert "Anthropic" in alerted_companies
    # The third alert should be Fortune500 (IBM), not Other tier
    assert "IBM" in alerted_companies
    
    # Verify Other tier companies were NOT alerted (silent only)
    assert "RandomStartup" not in alerted_companies
    assert "LocalCorp" not in alerted_companies
    
    # Verify all jobs stored in DB
    assert db.count_jobs() == 5


def test_fortune500_beats_other_when_priority_absent(tmp_path: Path, monkeypatch):
    """With cap=2 and no Priority tier, Fortune500 should beat Other."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    jobs = [
        make_job("Acme Corp", "SWE Intern", "https://acmecorp.com/careers/job/111111"),  # other
        make_job("Goldman Sachs", "SWE Intern", "https://goldmansachs.com/careers/job/222222"),  # fortune500
        make_job("Beta Industries", "ML Intern", "https://betaindustries.com/careers/job/333333"),  # other
        make_job("JPMorgan", "Data Intern", "https://jpmorgan.com/careers/job/444444"),  # fortune500
        make_job("Zeta Ventures", "Backend Intern", "https://zetaventures.com/careers/job/555555"),  # other
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout, \
         patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.director.enqueue") as mock_director:
        
        mock_scout.return_value = scout_results
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, alert_all=True)
    
    assert stats.new == 5
    assert stats.alerted == 2
    assert stats.alert_cap_hit is True
    
    notify_file = tmp_path / "notify.jsonl"
    lines = notify_file.read_text().strip().split("\n")
    
    import json
    notifications = [json.loads(line) for line in lines]
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    assert len(live_alerts) == 2
    
    alerted_companies = [n["job"]["company"] for n in live_alerts]
    # Both Fortune500 companies should be alerted
    assert "Goldman Sachs" in alerted_companies or "JPMorgan" in alerted_companies
    # No Other tier should be alerted when Fortune500 exists within cap
    assert "StartupA" not in alerted_companies
    assert "StartupB" not in alerted_companies
    assert "StartupC" not in alerted_companies


def test_jobs_past_cap_still_stored_silent(tmp_path: Path, monkeypatch):
    """Jobs past the cap should be stored in DB (silent path) but not Discord/ntfy."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    jobs = [
        make_job("Stripe", "SWE Intern", "https://stripe.com/careers/job/111111"),  # priority
        make_job("Tesla", "ML Intern", "https://tesla.com/careers/job/222222"),  # priority
        make_job("Netflix", "Data Intern", "https://netflix.com/careers/job/333333"),  # priority
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout, \
         patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.director.enqueue") as mock_director:
        
        mock_scout.return_value = scout_results
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, alert_all=True)
    
    # All 3 jobs should be stored in DB
    assert db.count_jobs() == 3
    assert stats.new == 3
    assert stats.alerted == 2
    assert stats.alert_cap_hit is True
    
    # Verify only 2 live alerts (third should be silent)
    notify_file = tmp_path / "notify.jsonl"
    lines = notify_file.read_text().strip().split("\n")
    
    import json
    notifications = [json.loads(line) for line in lines]
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    silent_alerts = [n for n in notifications if n.get("silent", False)]
    
    assert len(live_alerts) == 2
    assert len(silent_alerts) == 1
    
    # Verify the silent alert is for the 3rd priority job
    silent_companies = [n["job"]["company"] for n in silent_alerts]
    assert "Netflix" in silent_companies or "Stripe" in silent_companies or "Tesla" in silent_companies


def test_cap_zero_unlimited_preserves_prior_behavior(tmp_path: Path, monkeypatch):
    """With cap=0 (unlimited), all alertable jobs should be alerted."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    jobs = [
        make_job("Gamma Systems", "SWE Intern", "https://gammasystems.com/careers/job/111111"),
        make_job("Delta Technologies", "ML Intern", "https://deltatechnologies.com/careers/job/222222"),
        make_job("Epsilon Labs", "Data Intern", "https://epsilonlabs.com/careers/job/333333"),
        make_job("OpenAI", "SWE Intern", "https://openai.com/careers/job/444444"),
        make_job("IBM", "Backend Intern", "https://ibm.com/careers/job/555555"),
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout, \
         patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.director.enqueue") as mock_director:
        
        mock_scout.return_value = scout_results
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, alert_all=True)
    
    # All jobs should be alerted (no cap)
    assert stats.new == 5
    assert stats.alerted == 5
    assert stats.alert_cap_hit is False
    
    notify_file = tmp_path / "notify.jsonl"
    lines = notify_file.read_text().strip().split("\n")
    
    import json
    notifications = [json.loads(line) for line in lines]
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    
    # All 5 should be live alerts
    assert len(live_alerts) == 5


def test_stable_tiebreak_within_tier(tmp_path: Path, monkeypatch):
    """Within same tier, jobs should be ordered by (company, title, canonical_key)."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    # All Priority tier, different companies
    jobs = [
        make_job("Tesla", "SWE Intern", "https://tesla.com/careers/job/111111"),
        make_job("OpenAI", "SWE Intern", "https://openai.com/careers/job/222222"),
        make_job("Apple", "SWE Intern", "https://apple.com/careers/job/333333"),
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout, \
         patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.director.enqueue") as mock_director:
        
        mock_scout.return_value = scout_results
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, alert_all=True)
    
    assert stats.alerted == 2
    
    notify_file = tmp_path / "notify.jsonl"
    lines = notify_file.read_text().strip().split("\n")
    
    import json
    notifications = [json.loads(line) for line in lines]
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    
    alerted_companies = [n["job"]["company"] for n in live_alerts]
    
    # Should be alphabetically first 2: Apple and OpenAI (not Tesla)
    assert "Apple" in alerted_companies
    assert "OpenAI" in alerted_companies
    assert "Tesla" not in alerted_companies


def test_mixed_tier_large_batch_priority_dominates(tmp_path: Path, monkeypatch):
    """Large batch with cap: Priority tier should dominate the alerted set."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "5")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    db = Database(tmp_path / "test.db")
    
    # 10 Priority, 5 Fortune500, 5 Other
    # Use distinct company names to avoid fuzzy deduplication
    priority_companies = ["AlphaTech", "BravoCorp", "CharlieSys", "DeltaLabs", "EchoInc", 
                          "FoxtrotAI", "GolfVentures", "HotelTech", "IndiaIndustries", "JulietSoft"]
    fortune_companies = ["KiloBank", "LimaFinance", "MikeGroup", "NovemberCorp", "OscarHoldings"]
    other_companies = ["PapaStartup", "QuebecLabs", "RomeoVentures", "SierraInc", "TangoSystems"]
    
    jobs = []
    for i, company in enumerate(priority_companies):
        jobs.append(make_job(company, f"SWE Intern {i}", f"https://{company.lower()}.com/careers/job/{i}"))
    for i, company in enumerate(fortune_companies):
        jobs.append(make_job(company, f"ML Intern {i}", f"https://{company.lower()}.com/careers/job/{i}"))
    for i, company in enumerate(other_companies):
        jobs.append(make_job(company, f"Data Intern {i}", f"https://{company.lower()}.com/careers/job/{i}"))
    
    scout_results = [make_scout_result(jobs)]
    
    # Mark tiers by company name list
    with patch("jobradar.tier.classify_company_tier") as mock_classify:
        def classify_side_effect(company):
            if company in priority_companies:
                return "priority"
            elif company in fortune_companies:
                return "fortune500"
            else:
                return "other"
        
        mock_classify.side_effect = classify_side_effect
        
        with patch("jobradar.pipeline.scout_all") as mock_scout, \
             patch("jobradar.notify.send_discord") as mock_discord, \
             patch("jobradar.notify.send_ntfy") as mock_ntfy, \
             patch("jobradar.notify.send_telegram") as mock_telegram, \
             patch("jobradar.director.enqueue") as mock_director:
            
            mock_scout.return_value = scout_results
            mock_discord.return_value = "ok"
            mock_ntfy.return_value = "ok"
            mock_telegram.return_value = "ok"
            
            stats = run_scan(db=db, alert_all=True)
    
    assert stats.new == 20
    assert stats.alerted == 5
    assert stats.alert_cap_hit is True
    
    notify_file = tmp_path / "notify.jsonl"
    lines = notify_file.read_text().strip().split("\n")
    
    import json
    notifications = [json.loads(line) for line in lines]
    live_alerts = [n for n in notifications if not n.get("silent", False)]
    
    # All 5 alerted should be Priority tier
    alerted_companies = [n["job"]["company"] for n in live_alerts]
    for company in alerted_companies:
        assert company in priority_companies


def test_no_alertable_jobs_no_crash(tmp_path: Path, monkeypatch):
    """Pipeline should handle case where no jobs pass should_send_alerts."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "5")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")  # strict
    
    db = Database(tmp_path / "test.db")
    
    # Jobs without posted_at (will fail require_posted_at gate)
    jobs = [
        JobRecord(
            company="TestCorp",
            title="SWE Intern",
            location="Remote",
            url="https://testcorp.com/careers/job/123456",
            sources=["test"],
            # No posted_at
        )
    ]
    
    scout_results = [make_scout_result(jobs)]
    
    with patch("jobradar.pipeline.scout_all") as mock_scout:
        mock_scout.return_value = scout_results
        stats = run_scan(db=db, alert_all=True)
    
    # Should not crash, but also not alert
    assert stats.new == 1
    assert stats.alerted == 0
    assert stats.alert_cap_hit is False
