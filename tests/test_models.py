from jobradar.models import JobRecord, canonical_key, normalize_url


def test_canonical_key_from_url():
    a = canonical_key("A", "T", "SF", "https://example.com/job/1")
    b = canonical_key("B", "Other", "NY", "https://example.com/job/1")
    assert a == b
    assert a.startswith("url:")


def test_canonical_key_without_url():
    k = canonical_key("OpenAI", "Software Engineer Intern", "San Francisco, CA")
    assert "openai" in k
    assert "software" in k


def test_jobrecord_webhook_payload():
    job = JobRecord(
        company="OpenAI",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://example.com/job",
        sources=["simplify-summer-2027"],
        snippet="x" * 600,
        priority=True,
    )
    payload = job.webhook_payload()
    assert payload["event"] == "jobradar.new_job"
    assert payload["job"]["company"] == "OpenAI"
    assert len(payload["job"]["snippet"]) == 500
    assert payload["job"]["priority"] is True


def test_normalize_url_strips_utm_params():
    """URL normalization removes utm_* tracking parameters."""
    base = "https://hudl.com/careers/job/123"
    url1 = f"{base}?utm_source=aprameyak"
    url2 = f"{base}?utm_source=Simplify&ref=Simplify"
    url3 = f"{base}?utm_campaign=fall2027&utm_medium=email"
    
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    norm3 = normalize_url(url3)
    
    # All should normalize to the base URL (no query params)
    assert norm1 == base
    assert norm2 == base
    assert norm3 == base


def test_normalize_url_preserves_job_params():
    """URL normalization keeps job-identifying parameters."""
    url = "https://boards.greenhouse.io/company/jobs/123?gh_jid=456&utm_source=linkedin"
    normalized = normalize_url(url)
    
    # Should keep gh_jid but strip utm_source
    assert "gh_jid=456" in normalized
    assert "utm_source" not in normalized


def test_normalize_url_strips_fragments():
    """URL normalization removes fragment identifiers."""
    url = "https://example.com/job/123#apply"
    normalized = normalize_url(url)
    assert "#" not in normalized
    assert normalized == "https://example.com/job/123"


def test_normalize_url_trailing_slash():
    """URL normalization removes trailing slashes consistently."""
    url1 = "https://example.com/job/123/"
    url2 = "https://example.com/job/123"
    
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    
    assert norm1 == norm2
    assert norm1 == "https://example.com/job/123"


def test_normalize_url_sorts_query_params():
    """URL normalization sorts query parameters for consistency."""
    url1 = "https://example.com/job?b=2&a=1"
    url2 = "https://example.com/job?a=1&b=2"
    
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    
    assert norm1 == norm2


def test_canonical_key_identical_with_different_tracking():
    """Same job with different tracking parameters gets same canonical_key."""
    company = "Hudl"
    title = "Product Management Intern"
    location = "Remote"
    
    # Same job, different tracking params
    url1 = "https://hudl.com/careers/job/123?utm_source=aprameyak"
    url2 = "https://hudl.com/careers/job/123?utm_source=Simplify&ref=Simplify"
    
    key1 = canonical_key(company, title, location, url1)
    key2 = canonical_key(company, title, location, url2)
    
    assert key1 == key2
    assert key1.startswith("url:")


def test_canonical_key_different_for_different_urls():
    """Different job URLs should still get different canonical_keys."""
    company = "Hudl"
    title = "Product Management Intern"
    location = "Remote"
    
    url1 = "https://hudl.com/careers/job/123"
    url2 = "https://hudl.com/careers/job/456"
    
    key1 = canonical_key(company, title, location, url1)
    key2 = canonical_key(company, title, location, url2)
    
    assert key1 != key2


def test_normalize_url_workday_variants():
    """Workday URLs with different tracking params should normalize identically."""
    base = "https://myworkdayjobs.com/company/job/Engineer/SWE-Intern_JR12345"
    url1 = f"{base}?source=LinkedIn"
    url2 = f"{base}?source=Indeed&ref=external"
    
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    
    assert norm1 == norm2
    assert norm1 == base


def test_normalize_url_empty_company_title_location():
    """Empty URL falls back to company|title|location key (unchanged behavior)."""
    key1 = canonical_key("Hudl", "PM Intern", "Remote", "")
    key2 = canonical_key("Hudl", "PM Intern", "Remote", "")
    
    assert key1 == key2
    assert not key1.startswith("url:")
    assert "hudl" in key1
    assert "pm" in key1
