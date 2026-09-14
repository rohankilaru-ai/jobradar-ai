"""Tests for specific job URL detection.

Ensures generic career search/listing pages are blocked while specific job postings are allowed.
"""

import pytest

from jobradar.models import JobRecord
from jobradar.notify import is_specific_job_url, job_notify_block_reason


class TestIsSpecificJobUrl:
    """Test the is_specific_job_url helper."""

    def test_blocks_dreamworkhq_aggregator(self):
        """dreamworkhq.com is an aggregator, not an employer ATS."""
        assert is_specific_job_url("https://dreamworkhq.com/jobs") is False
        assert is_specific_job_url("http://dreamworkhq.com/tech-jobs") is False
        assert is_specific_job_url("https://www.dreamworkhq.com/careers") is False

    def test_blocks_generic_careers_homepage(self):
        """Block /careers, /jobs without job IDs."""
        assert is_specific_job_url("https://tesla.com/careers") is False
        assert is_specific_job_url("https://google.com/careers/") is False
        assert is_specific_job_url("https://apple.com/jobs") is False
        assert is_specific_job_url("https://netflix.com/jobs/") is False

    def test_blocks_careers_search_pages(self):
        """Block career search/results pages."""
        # Tesla-style
        assert is_specific_job_url("https://tesla.com/careers/search") is False
        assert is_specific_job_url("https://tesla.com/careers/search/") is False
        assert is_specific_job_url("https://www.tesla.com/careers/search?query=intern") is False
        
        # Google-style
        assert is_specific_job_url("https://google.com/about/careers/applications/results") is False
        assert is_specific_job_url("https://careers.google.com/jobs/results") is False
        
        # Microsoft-style
        assert is_specific_job_url("https://apply.careers.microsoft.com/careers?query=intern") is False
        assert is_specific_job_url("https://careers.microsoft.com/us/en/search-results") is False
        
        # Generic patterns
        assert is_specific_job_url("https://company.com/careers/openings") is False
        assert is_specific_job_url("https://company.com/job-listings") is False
        assert is_specific_job_url("https://company.com/careers?department=engineering") is False

    def test_allows_greenhouse_specific_jobs(self):
        """Greenhouse URLs with job IDs should pass."""
        assert is_specific_job_url("https://boards.greenhouse.io/stripe/jobs/123456") is True
        assert is_specific_job_url("https://boards.greenhouse.io/openai/jobs/5678?gh_jid=5678") is True
        assert is_specific_job_url("https://greenhouse.io/company/jobs/789") is True

    def test_allows_lever_specific_jobs(self):
        """Lever URLs with job slugs should pass."""
        assert is_specific_job_url("https://jobs.lever.co/stripe/abc-123") is True
        assert is_specific_job_url("https://jobs.lever.co/openai/software-engineer-intern") is True

    def test_allows_ashby_specific_jobs(self):
        """Ashby URLs with job UUIDs should pass."""
        assert is_specific_job_url("https://jobs.ashbyhq.com/stripe/12345678-abcd-1234-abcd-123456789012") is True
        assert is_specific_job_url("https://ashbyhq.com/stripe/abc123") is True

    def test_allows_workday_specific_jobs(self):
        """Workday URLs with /job/ path should pass."""
        assert is_specific_job_url("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Intern_JR123") is True
        assert is_specific_job_url("https://company.myworkdayjobs.com/careers/job/Software-Engineer") is True

    def test_allows_icims_specific_jobs(self):
        """iCIMS URLs with /job path should pass."""
        assert is_specific_job_url("https://careers.icims.com/company/jobs/12345") is True
        assert is_specific_job_url("https://apply.icims.com/careers/job?job=456") is True

    def test_allows_amazon_jobs_specific_postings(self):
        """Amazon.jobs URLs with /jobs/ path should pass."""
        assert is_specific_job_url("https://amazon.jobs/en/jobs/12345/software-engineer-intern") is True
        assert is_specific_job_url("https://www.amazon.jobs/jobs/123456") is True

    def test_allows_company_pages_with_job_identifiers(self):
        """Company career pages with job identifiers should pass."""
        # gh_jid parameter (Greenhouse)
        assert is_specific_job_url("https://stripe.com/jobs/listing?gh_jid=12345") is True
        assert is_specific_job_url("https://company.com/careers?gh_jid=67890") is True
        
        # /position/ path
        assert is_specific_job_url("https://janestreet.com/join-jane-street/position/7527629002") is True
        assert is_specific_job_url("https://company.com/careers/position/12345") is True
        
        # /job/ path with ID-like segment
        assert is_specific_job_url("https://microsoft.com/careers/job/12345") is True
        assert is_specific_job_url("https://google.com/careers/jobs/123456789") is True
        
        # Job ID in query parameters
        assert is_specific_job_url("https://company.com/careers?job_id=12345") is True
        assert is_specific_job_url("https://company.com/apply?id=67890") is True

    def test_allows_urls_with_job_in_path_and_identifier(self):
        """URLs with /job/ or /jobs/ followed by identifier should pass."""
        assert is_specific_job_url("https://meta.com/careers/jobs/987654321") is True
        assert is_specific_job_url("https://netflix.com/jobs/intern-2025") is True
        assert is_specific_job_url("https://company.com/job/software-engineer-123") is True

    def test_blocks_jobs_path_without_specific_identifier(self):
        """Block /jobs without specific identifier."""
        # Just /jobs or /careers
        assert is_specific_job_url("https://company.com/jobs") is False
        assert is_specific_job_url("https://company.com/careers") is False
        
        # /jobs/results, /jobs/search are listing pages
        assert is_specific_job_url("https://company.com/jobs/results") is False
        assert is_specific_job_url("https://company.com/jobs/search") is False

    def test_allows_taleo_specific_jobs(self):
        """Taleo URLs with job IDs should pass."""
        assert is_specific_job_url("https://company.taleo.net/careersection/jobdetail.ftl?job=12345") is True
        assert is_specific_job_url("https://tbe.taleo.net/careers/job?id=67890") is True

    def test_allows_smartrecruiters_specific_jobs(self):
        """SmartRecruiters URLs with job IDs should pass."""
        assert is_specific_job_url("https://jobs.smartrecruiters.com/Company/12345") is True
        assert is_specific_job_url("https://company.smartrecruiters.com/jobs/67890") is True

    def test_handles_edge_cases(self):
        """Handle edge cases gracefully."""
        # Empty/None
        assert is_specific_job_url("") is False
        assert is_specific_job_url(None) is False
        
        # Not HTTP(S)
        assert is_specific_job_url("javascript:void(0)") is False
        assert is_specific_job_url("mailto:jobs@company.com") is False


class TestJobNotifyBlockReasonWithGenericUrls:
    """Test that job_notify_block_reason blocks generic career pages."""

    def test_blocks_dreamworkhq_aggregator(self):
        """dreamworkhq.com URLs should be blocked."""
        job = JobRecord(
            company="Some Company",
            title="Software Engineer Intern",
            url="https://dreamworkhq.com/jobs/listing",
        )
        reason = job_notify_block_reason(job)
        assert reason is not None
        assert "generic career page" in reason.lower() or "not a specific job" in reason.lower()

    def test_blocks_tesla_careers_search(self):
        """Tesla career search page should be blocked."""
        job = JobRecord(
            company="Tesla",
            title="Software Engineer Intern",
            url="https://tesla.com/careers/search",
        )
        reason = job_notify_block_reason(job)
        assert reason is not None
        assert "generic career page" in reason.lower() or "not a specific job" in reason.lower()

    def test_blocks_google_careers_results(self):
        """Google career results page should be blocked."""
        job = JobRecord(
            company="Google",
            title="Software Engineer Intern",
            url="https://google.com/about/careers/applications/results",
        )
        reason = job_notify_block_reason(job)
        assert reason is not None
        assert "generic career page" in reason.lower() or "not a specific job" in reason.lower()

    def test_blocks_microsoft_careers_query(self):
        """Microsoft career query page should be blocked."""
        job = JobRecord(
            company="Microsoft",
            title="Software Engineer Intern",
            url="https://apply.careers.microsoft.com/careers?query=intern",
        )
        reason = job_notify_block_reason(job)
        assert reason is not None
        assert "generic career page" in reason.lower() or "not a specific job" in reason.lower()

    def test_allows_greenhouse_specific_job(self):
        """Greenhouse specific job URL should not be blocked."""
        job = JobRecord(
            company="Stripe",
            title="Software Engineer Intern",
            url="https://boards.greenhouse.io/stripe/jobs/123456",
        )
        # Mock probe to return True
        from unittest.mock import patch
        with patch("jobradar.notify.probe_url", return_value=True):
            reason = job_notify_block_reason(job)
            assert reason is None

    def test_allows_company_page_with_gh_jid(self):
        """Company page with gh_jid parameter should not be blocked."""
        job = JobRecord(
            company="Stripe",
            title="Software Engineer Intern",
            url="https://stripe.com/jobs/listing?gh_jid=12345",
        )
        from unittest.mock import patch
        with patch("jobradar.notify.probe_url", return_value=True):
            reason = job_notify_block_reason(job)
            assert reason is None

    def test_allows_company_page_with_position_path(self):
        """Company page with /position/ path should not be blocked."""
        job = JobRecord(
            company="Jane Street",
            title="Software Engineer",
            url="https://janestreet.com/join-jane-street/position/7527629002",
        )
        from unittest.mock import patch
        with patch("jobradar.notify.probe_url", return_value=True):
            reason = job_notify_block_reason(job)
            assert reason is None
