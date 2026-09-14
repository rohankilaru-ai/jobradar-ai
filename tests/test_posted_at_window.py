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
