"""posted_at should gate Discord notify window."""

from datetime import datetime, timedelta, timezone

from jobradar.classify import should_keep
from jobradar.models import JobRecord
from jobradar.notify import within_notify_window
from jobradar.parsers import parse_aprameyak_json


def test_aprameyak_date_added_maps_to_posted_at():
    raw = '''[{"company":"Acme","role":"SWE Intern","location":"SF","url":"https://boards.greenhouse.io/acme/jobs/1","date_added":"2026-07-07"}]'''
    jobs = parse_aprameyak_json(raw)
    assert jobs[0].posted_at == "2026-07-07"


def test_old_posted_at_outside_notify_window():
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://boards.greenhouse.io/acme/jobs/1",
        posted_at="2026-07-07",
        first_seen_at=datetime.now(timezone.utc).isoformat(),
    )
    assert within_notify_window(job) is False


def test_recent_posted_at_inside_notify_window():
    posted = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://boards.greenhouse.io/acme/jobs/2",
        posted_at=posted,
    )
    assert within_notify_window(job) is True


def test_new_grad_without_intern_dropped():
    assert should_keep(JobRecord(company="X", title="Software Engineer, New Grad", url="https://boards.greenhouse.io/x/jobs/1")) is False
    assert should_keep(JobRecord(company="X", title="Early Career Software Engineer", url="https://boards.greenhouse.io/x/jobs/2")) is False
    assert should_keep(JobRecord(company="X", title="Software Engineer Intern", url="https://boards.greenhouse.io/x/jobs/3")) is True


def test_age_token_1mo_outside_two_week_window():
    from datetime import datetime, timezone
    from jobradar.parsers import age_token_to_posted_at
    from jobradar.models import JobRecord
    from jobradar.notify import within_notify_window

    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    posted = age_token_to_posted_at("1mo", now=now)
    assert posted == "2026-08-15"
    job = JobRecord(
        company="SpaceX",
        title="Software Engineering Intern/Co-op",
        first_seen_at=now.isoformat(),
        posted_at=posted,
    )
    assert within_notify_window(job, now=now) is False


def test_phd_masters_postgrad_filtered():
    assert should_keep(JobRecord(company="Google", title="Software Engineering Intern, PhD, Summer 2027", url="https://x/1")) is False
    assert should_keep(JobRecord(company="Marvell", title="IC Validation Engineer Intern - MS", url="https://x/2")) is False
    assert should_keep(JobRecord(company="X", title="Postgraduate Research Intern", url="https://x/3")) is False
    # undergrad dual-track still kept
    assert should_keep(JobRecord(company="Y", title="Software Engineer Intern BS/MS", url="https://x/4")) is True
    assert should_keep(JobRecord(company="Z", title="Software Engineer Intern", url="https://x/5")) is True


def test_missing_posted_at_blocked_by_default(monkeypatch):
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://boards.greenhouse.io/acme/jobs/3",
        posted_at="",
        first_seen_at=datetime.now(timezone.utc).isoformat(),
    )
    assert within_notify_window(job) is False


def test_missing_posted_at_allowed_when_require_off(monkeypatch):
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://boards.greenhouse.io/acme/jobs/4",
        posted_at="",
        first_seen_at=datetime.now(timezone.utc).isoformat(),
    )
    assert within_notify_window(job) is True


def test_four_day_old_posted_outside_three_day_window():
    posted = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://boards.greenhouse.io/acme/jobs/9",
        posted_at=posted,
        first_seen_at=datetime.now(timezone.utc).isoformat(),
    )
    assert within_notify_window(job) is False
