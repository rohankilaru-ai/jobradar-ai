from pathlib import Path

from jobradar.parsers import (
    parse_applyguy_json,
    parse_aprameyak_json,
    parse_dreamwork_json,
    parse_markdown_table,
    parse_simplify_html,
)

FIX = Path(__file__).parent / "fixtures"


def test_aprameyak():
    jobs = parse_aprameyak_json((FIX / "aprameyak_sample.json").read_text())
    assert any(j.company == "OpenAI" for j in jobs)
    assert len(jobs) == 2


def test_dreamwork():
    jobs = parse_dreamwork_json((FIX / "dreamwork_sample.json").read_text())
    assert jobs[0].company == "Databricks"
    assert "Data Engineering" in jobs[0].title


def test_applyguy():
    jobs = parse_applyguy_json((FIX / "applyguy_sample.json").read_text())
    assert jobs[0].company == "Stripe"
    assert "stripe.com" in jobs[0].url


def test_simplify_html_inherit_and_inactive():
    jobs = parse_simplify_html((FIX / "simplify_sample.md").read_text())
    companies = [j.company for j in jobs]
    assert companies.count("OpenAI") == 2  # parent + ↳ child
    assert all(j.company != "InactiveCorp" for j in jobs)
    child = next(j for j in jobs if "Research" in j.title)
    assert child.is_closed is True
    assert child.url.startswith("https://openai.com")


def test_markdown_table_inherit_and_closed():
    jobs = parse_markdown_table((FIX / "vansh_sample.md").read_text(), source="vansh")
    assert [j.company for j in jobs] == ["OpenAI", "OpenAI", "Acme"]
    research = next(j for j in jobs if "Research" in j.title)
    assert research.is_closed is True
    assert research.url.startswith("https://openai.com/careers/research")
