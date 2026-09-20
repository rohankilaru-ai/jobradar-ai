"""Tests for parser HTML/URL hardening (overnight #11)."""

import json
from pathlib import Path

import pytest

from jobradar.parsers import (
    parse_aprameyak_json,
    parse_applyguy_json,
    parse_dreamwork_json,
    parse_markdown_table,
    parse_simplify_html,
)

FIX = Path(__file__).parent / "fixtures"


class TestSimplifyHTMLHardening:
    """Test Simplify HTML parser robustness."""

    def test_broken_rows_insufficient_columns(self):
        """Parser should skip rows with fewer than 3 columns."""
        html = """
        <table>
        <tr><td>OnlyOne</td></tr>
        <tr><td>Two</td><td>Columns</td></tr>
        <tr><td>Good Company</td><td>SWE Intern</td><td>SF</td><td><a href="https://good.com/job">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 1
        assert jobs[0].company == "Good Company"

    def test_empty_cells(self):
        """Parser should handle empty cells gracefully."""
        html = """
        <table>
        <tr><td></td><td>Title Only</td><td>SF</td><td></td></tr>
        <tr><td>Company</td><td></td><td>NYC</td><td></td></tr>
        <tr><td>Good</td><td>SWE Intern</td><td>Remote</td><td><a href="https://good.com/job">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        # First two should be skipped (no title or no company)
        assert len(jobs) == 1
        assert jobs[0].company == "Good"

    def test_inactive_in_multiple_fields(self):
        """Inactive marker should be detected in company, title, or location."""
        html = """
        <table>
        <tr><td>Inactive Corp</td><td>SWE Intern</td><td>SF</td><td><a href="https://x.com">Apply</a></td></tr>
        <tr><td>Good Co</td><td>Inactive Position</td><td>SF</td><td><a href="https://x.com">Apply</a></td></tr>
        <tr><td>Another Co</td><td>SWE Intern</td><td>Inactive NYC</td><td><a href="https://x.com">Apply</a></td></tr>
        <tr><td>Valid Co</td><td>SWE Intern</td><td>SF</td><td><a href="https://valid.com/job">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 1
        assert jobs[0].company == "Valid Co"

    def test_inherit_marker_without_previous_company(self):
        """↳ marker at start should be skipped (no previous company)."""
        html = """
        <table>
        <tr><td>↳</td><td>Orphan Role</td><td>SF</td><td><a href="https://x.com">Apply</a></td></tr>
        <tr><td>Good Co</td><td>SWE Intern</td><td>NYC</td><td><a href="https://good.com/job">Apply</a></td></tr>
        <tr><td>↳</td><td>Child Role</td><td>SF</td><td><a href="https://good.com/job2">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 2
        assert jobs[0].company == "Good Co"
        assert jobs[1].company == "Good Co"  # Inherited

    def test_inherit_url_from_parent(self):
        """↳ row without URL should inherit from parent."""
        html = """
        <table>
        <tr><td>OpenAI</td><td>SWE Intern</td><td>SF</td><td><a href="https://openai.com/job1">Apply</a></td></tr>
        <tr><td>↳</td><td>Research Intern</td><td>SF</td><td></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 2
        assert jobs[0].url == "https://openai.com/job1"
        assert jobs[1].url == "https://openai.com/job1"  # Inherited

    def test_bad_url_rejected_at_parse_time(self):
        """Bad URLs (example.com, etc.) should be rejected."""
        html = """
        <table>
        <tr><td>BadCo</td><td>SWE Intern</td><td>SF</td><td><a href="http://example.com">Apply</a></td></tr>
        <tr><td>LocalCo</td><td>SWE Intern</td><td>NYC</td><td><a href="http://localhost:3000">Apply</a></td></tr>
        <tr><td>GoodCo</td><td>SWE Intern</td><td>Remote</td><td><a href="https://goodco.com/jobs/123">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 3
        # Bad URLs should be empty strings
        assert jobs[0].url == ""
        assert jobs[1].url == ""
        assert jobs[2].url == "https://goodco.com/jobs/123"

    def test_generic_career_pages_rejected(self):
        """Generic career search pages should be rejected."""
        html = """
        <table>
        <tr><td>Co1</td><td>SWE Intern</td><td>SF</td><td><a href="https://company.com/careers">Apply</a></td></tr>
        <tr><td>Co2</td><td>SWE Intern</td><td>NYC</td><td><a href="https://company.com/careers/search">Apply</a></td></tr>
        <tr><td>Co3</td><td>SWE Intern</td><td>Remote</td><td><a href="https://company.com/careers/position/123">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 3
        # Generic career pages should be rejected
        assert jobs[0].url == ""
        assert jobs[1].url == ""
        # Specific position URL should be kept
        assert jobs[2].url == "https://company.com/careers/position/123"

    def test_malformed_html_does_not_crash(self):
        """Parser should handle malformed HTML gracefully."""
        html = """
        <table>
        <tr><td>Unclosed tag
        <tr><td>Good Co</td><td>SWE Intern</td><td>SF</td><td><a href="https://good.com/job">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        # Should not crash, should extract at least the valid row
        assert len(jobs) >= 1
        assert any(j.company == "Good Co" for j in jobs)

    def test_url_cleaning_strips_junk(self):
        """URL cleaning should strip trailing quotes and junk."""
        html = """
        <table>
        <tr><td>Co1</td><td>SWE</td><td>SF</td><td><a href="https://jobs.lever.co/company/123">Apply</a></td></tr>
        <tr><td>Co2</td><td>SWE</td><td>SF</td><td><a href="https://boards.greenhouse.io/company/456">Apply</a></td></tr>
        <tr><td>Co3</td><td>SWE</td><td>SF</td><td><a href="https://company.com/careers/position/789">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 3
        # All should have valid URLs
        assert "lever.co" in jobs[0].url
        assert "greenhouse.io" in jobs[1].url
        assert "position/789" in jobs[2].url

    def test_empty_company_after_inheritance(self):
        """Empty company cell with explicit ↳ should be treated as inherit."""
        html = """
        <table>
        <tr><td>OpenAI</td><td>SWE Intern</td><td>SF</td><td><a href="https://openai.com/job1">Apply</a></td></tr>
        <tr><td>↳</td><td>Research Intern</td><td>SF</td><td><a href="https://openai.com/job2">Apply</a></td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 2
        assert jobs[1].company == "OpenAI"  # Inherited


class TestMarkdownTableHardening:
    """Test Markdown table parser robustness."""

    def test_broken_rows_insufficient_columns(self):
        """Parser should handle rows with fewer columns than header."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | TwoColumns | Only |
        | Good Co | SWE Intern | SF | https://good.com/job |
        """
        jobs = parse_markdown_table(md)
        # Parser handles missing columns gracefully (fills with empty strings)
        assert len(jobs) == 2
        assert jobs[0].company == "TwoColumns"
        assert jobs[0].location == ""  # Missing column
        assert jobs[1].company == "Good Co"

    def test_no_header_rows_skipped(self):
        """Data rows before header should be skipped."""
        md = """
        | Bad | Data | Here |
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | Good Co | SWE Intern | SF | https://good.com/job |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 1
        assert jobs[0].company == "Good Co"

    def test_inherit_without_previous_company(self):
        """↳ at start should be skipped."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | ↳ | Orphan Role | SF | https://x.com |
        | Good Co | SWE Intern | NYC | https://good.com/job |
        | ↳ | Child Role | SF | https://good.com/job2 |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 2
        assert jobs[0].company == "Good Co"
        assert jobs[1].company == "Good Co"

    def test_inherit_url_from_parent(self):
        """↳ row without URL should inherit from parent."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | OpenAI | SWE Intern | SF | https://openai.com/job1 |
        | ↳ | Research Intern | SF | |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 2
        assert jobs[1].url == "https://openai.com/job1"

    def test_bad_url_rejected(self):
        """Bad URLs should be rejected."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | BadCo | SWE | SF | http://example.com |
        | GoodCo | SWE | NYC | https://goodco.com/jobs/123 |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 2
        assert jobs[0].url == ""
        assert jobs[1].url == "https://goodco.com/jobs/123"

    def test_empty_cells(self):
        """Empty company or title should skip row."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | | No Company | SF | https://x.com |
        | Has Company | | NYC | https://y.com |
        | Good Co | SWE Intern | Remote | https://good.com/job |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 1
        assert jobs[0].company == "Good Co"


class TestJSONParserHardening:
    """Test JSON parser robustness."""

    def test_aprameyak_invalid_json(self):
        """Invalid JSON should return empty list, not crash."""
        jobs = parse_aprameyak_json("not valid json")
        assert jobs == []

    def test_aprameyak_not_a_list(self):
        """Non-list JSON should return empty list."""
        jobs = parse_aprameyak_json('{"company": "X"}')
        assert jobs == []

    def test_aprameyak_missing_fields(self):
        """Items missing company or title should be skipped."""
        data = [
            {"company": "Co1"},  # No title
            {"title": "SWE"},  # No company
            {"company": "Good Co", "role": "SWE Intern", "url": "https://good.com/job"},
        ]
        jobs = parse_aprameyak_json(json.dumps(data))
        assert len(jobs) == 1
        assert jobs[0].company == "Good Co"

    def test_aprameyak_bad_url_rejected(self):
        """Bad URLs should be cleaned/rejected."""
        data = [
            {"company": "BadCo", "role": "SWE", "url": "http://example.com"},
            {"company": "GoodCo", "role": "SWE", "url": "https://goodco.com/jobs/123"},
        ]
        jobs = parse_aprameyak_json(json.dumps(data))
        assert len(jobs) == 2
        assert jobs[0].url == ""
        assert jobs[1].url == "https://goodco.com/jobs/123"

    def test_dreamwork_invalid_json(self):
        """Invalid JSON should return empty list."""
        jobs = parse_dreamwork_json("{bad json")
        assert jobs == []

    def test_dreamwork_missing_listings(self):
        """Missing listings array should return empty list."""
        jobs = parse_dreamwork_json('{"other": "data"}')
        assert jobs == []

    def test_dreamwork_missing_fields(self):
        """Items missing company or title should be skipped."""
        data = {
            "listings": [
                {"company": "Co1"},  # No title
                {"title": "SWE"},  # No company
                {"company": "Good Co", "title": "SWE Intern", "url": "https://good.com/job"},
            ]
        }
        jobs = parse_dreamwork_json(json.dumps(data))
        assert len(jobs) == 1
        assert jobs[0].company == "Good Co"

    def test_applyguy_invalid_json(self):
        """Invalid JSON should return empty list."""
        jobs = parse_applyguy_json("[invalid")
        assert jobs == []

    def test_applyguy_missing_jobs(self):
        """Missing jobs array should return empty list."""
        jobs = parse_applyguy_json('{"listings": []}')
        assert jobs == []

    def test_applyguy_missing_fields(self):
        """Items missing company or title should be skipped."""
        data = {
            "jobs": [
                {"company": "Co1"},  # No title
                {"title": "SWE"},  # No company
                {"company": "Good Co", "title": "SWE Intern", "listingUrl": "https://good.com/job"},
            ]
        }
        jobs = parse_applyguy_json(json.dumps(data))
        assert len(jobs) == 1
        assert jobs[0].company == "Good Co"

    def test_applyguy_bad_url_rejected(self):
        """Bad URLs should be cleaned/rejected."""
        data = {
            "jobs": [
                {"company": "BadCo", "title": "SWE", "listingUrl": "http://localhost:3000"},
                {"company": "GoodCo", "title": "SWE", "listingUrl": "https://goodco.com/jobs/123"},
            ]
        }
        jobs = parse_applyguy_json(json.dumps(data))
        assert len(jobs) == 2
        assert jobs[0].url == ""
        assert jobs[1].url == "https://goodco.com/jobs/123"


class TestURLNormalization:
    """Test URL cleaning and validation edge cases."""

    def test_simplify_redirects_skipped(self):
        """Simplify.jobs tracking URLs should be skipped."""
        html = """
        <table>
        <tr><td>Co1</td><td>SWE</td><td>SF</td><td>
            <a href="https://simplify.jobs/c/company123">Simplify</a>
            <a href="https://jobs.lever.co/stripe/123">Apply</a>
        </td></tr>
        </table>
        """
        jobs = parse_simplify_html(html)
        assert len(jobs) == 1
        # Should extract the real job URL, not the Simplify redirect
        assert "lever.co" in jobs[0].url
        assert "simplify.jobs" not in jobs[0].url

    def test_markdown_url_extraction_with_junk(self):
        """Markdown URL extraction should handle trailing punctuation."""
        md = """
        | Company | Role | Location | Link |
        | ------- | ---- | -------- | ---- |
        | Co1 | SWE | SF | https://jobs.lever.co/stripe/123 |
        | Co2 | SWE | NYC | https://boards.greenhouse.io/company/456 |
        """
        jobs = parse_markdown_table(md)
        assert len(jobs) == 2
        assert "lever.co" in jobs[0].url
        assert "greenhouse.io" in jobs[1].url


def test_parser_integration_with_existing_fixtures():
    """Ensure hardening doesn't break existing fixture tests."""
    # Simplify
    simplify_jobs = parse_simplify_html((FIX / "simplify_sample.md").read_text())
    assert len(simplify_jobs) >= 2
    assert any(j.company == "OpenAI" for j in simplify_jobs)
    assert all(j.company != "InactiveCorp" for j in simplify_jobs)

    # Markdown
    md_jobs = parse_markdown_table((FIX / "vansh_sample.md").read_text())
    assert len(md_jobs) >= 2
    assert any(j.company == "OpenAI" for j in md_jobs)


def test_prefer_fewer_clean_records():
    """Parser should prefer returning fewer clean records over garbage."""
    html = """
    <table>
    <tr><td>BadCo1</td><td>SWE</td><td>SF</td><td><a href="http://example.com">Bad</a></td></tr>
    <tr><td>BadCo2</td><td>SWE</td><td>SF</td><td><a href="">Empty</a></td></tr>
    <tr><td></td><td>SWE</td><td>SF</td><td><a href="https://x.com">NoCompany</a></td></tr>
    <tr><td>GoodCo</td><td>SWE Intern</td><td>Remote</td><td><a href="https://goodco.com/jobs/123">Apply</a></td></tr>
    </table>
    """
    jobs = parse_simplify_html(html)
    # Should extract all rows, but bad URLs should be empty strings
    # The third row (no company) should be skipped
    assert len(jobs) == 3
    valid_jobs = [j for j in jobs if j.url]
    assert len(valid_jobs) == 1
    assert valid_jobs[0].company == "GoodCo"
