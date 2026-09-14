from jobradar.models import JobRecord, canonical_key


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
