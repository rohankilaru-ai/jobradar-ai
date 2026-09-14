from jobradar.classify import is_priority_company, should_keep
from jobradar.db import Database
from jobradar.dedupe import is_duplicate
from jobradar.models import JobRecord
from jobradar.notify import MockNotifier, format_alert
from jobradar.pipeline import run_scan


def test_priority_and_exclude():
    assert is_priority_company("OpenAI")
    assert should_keep(JobRecord(company="X", title="Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Y", title="Nursing Intern")) is False


# --- Comprehensive exclude list tests ---


def test_exclude_medical_healthcare():
    """Medical and healthcare roles should be excluded."""
    assert should_keep(JobRecord(company="Hospital", title="Nursing Intern")) is False
    assert should_keep(JobRecord(company="Clinic", title="Registered Nurse Intern")) is False
    assert should_keep(JobRecord(company="Pharmacy", title="Pharmacist Intern")) is False
    assert should_keep(JobRecord(company="Dental Office", title="Dental Assistant Intern")) is False
    assert should_keep(JobRecord(company="Medical Center", title="Clinical Research Intern")) is False
    assert should_keep(JobRecord(company="Healthcare Co", title="Medical Assistant Intern")) is False
    assert should_keep(JobRecord(company="Hospital", title="Physician Intern")) is False
    assert should_keep(JobRecord(company="HealthTech", title="Healthcare Analyst Intern")) is False


def test_exclude_finance_accounting_nontechnical():
    """Non-technical finance and accounting roles should be excluded."""
    assert should_keep(JobRecord(company="Tax Firm", title="Tax Intern")) is False
    assert should_keep(JobRecord(company="Accounting Co", title="Tax Analyst Intern")) is False
    assert should_keep(JobRecord(company="Finance Co", title="Accounting Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Bookkeeper Intern")) is False
    assert should_keep(JobRecord(company="Business", title="Accounts Payable Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Accounts Receivable Intern")) is False
    assert should_keep(JobRecord(company="HR Dept", title="Payroll Intern")) is False


def test_exclude_legal():
    """Legal roles should be excluded."""
    assert should_keep(JobRecord(company="Law Firm", title="Legal Intern")) is False
    assert should_keep(JobRecord(company="Legal Services", title="Paralegal Intern")) is False
    assert should_keep(JobRecord(company="Law Office", title="Law Clerk")) is False
    assert should_keep(JobRecord(company="Legal Dept", title="Legal Assistant Intern")) is False


def test_exclude_hr_recruiting_admin():
    """HR, recruiting, and administrative roles should be excluded."""
    assert should_keep(JobRecord(company="Corp", title="HR Intern")) is False
    assert should_keep(JobRecord(company="Business", title="Human Resources Intern")) is False
    assert should_keep(JobRecord(company="Recruiting Co", title="Recruiter Intern")) is False
    assert should_keep(JobRecord(company="Office", title="Administrative Assistant Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Office Assistant Intern")) is False
    assert should_keep(JobRecord(company="Business", title="Receptionist Intern")) is False
    assert should_keep(JobRecord(company="Nonprofit", title="Social Work Intern")) is False


def test_exclude_sales_marketing_nontechnical():
    """Non-technical sales and marketing roles should be excluded."""
    assert should_keep(JobRecord(company="Marketing Co", title="Marketing Intern")) is False
    assert should_keep(JobRecord(company="Sales Corp", title="Sales Intern")) is False
    assert should_keep(JobRecord(company="Real Estate Co", title="Real Estate Intern")) is False
    assert should_keep(JobRecord(company="Business", title="Business Development Intern")) is False
    assert should_keep(JobRecord(company="Sales Co", title="Account Executive Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Sales Rep Intern")) is False
    assert should_keep(JobRecord(company="Retail", title="Sales Associate Intern")) is False


def test_exclude_content_media_nontechnical():
    """Non-technical content and media roles should be excluded."""
    assert should_keep(JobRecord(company="Media Co", title="Content Writer Intern")) is False
    assert should_keep(JobRecord(company="Agency", title="Copywriter Intern")) is False
    assert should_keep(JobRecord(company="News Co", title="Journalist Intern")) is False
    assert should_keep(JobRecord(company="Magazine", title="Editorial Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Communications Intern")) is False
    assert should_keep(JobRecord(company="PR Agency", title="Public Relations Intern")) is False
    assert should_keep(JobRecord(company="Marketing", title="PR Intern")) is False


def test_exclude_operations_logistics_nontechnical():
    """Non-technical operations and logistics roles should be excluded."""
    assert should_keep(JobRecord(company="Warehouse Co", title="Warehouse Intern")) is False
    assert should_keep(JobRecord(company="Logistics", title="Logistics Intern")) is False
    assert should_keep(JobRecord(company="Supply Chain Co", title="Supply Chain Intern")) is False
    assert should_keep(JobRecord(company="Operations", title="Operations Intern")) is False
    assert should_keep(JobRecord(company="Warehouse", title="Inventory Intern")) is False
    assert should_keep(JobRecord(company="Delivery Co", title="Driver Intern")) is False


def test_exclude_service_hospitality():
    """Service and hospitality roles should be excluded."""
    assert should_keep(JobRecord(company="Support Co", title="Customer Service Intern")) is False
    assert should_keep(JobRecord(company="Retail Store", title="Retail Intern")) is False
    assert should_keep(JobRecord(company="Store", title="Cashier Intern")) is False
    assert should_keep(JobRecord(company="Restaurant", title="Server Intern")) is False
    assert should_keep(JobRecord(company="Restaurant", title="Host Intern")) is False


def test_exclude_education_tutoring():
    """Education and tutoring roles should be excluded."""
    assert should_keep(JobRecord(company="School", title="Teacher Intern")) is False
    assert should_keep(JobRecord(company="Tutoring Co", title="Tutor Intern")) is False
    assert should_keep(JobRecord(company="University", title="Teaching Assistant")) is False
    assert should_keep(JobRecord(company="Summer Camp", title="Camp Counselor")) is False


def test_exclude_arts_design_nontechnical():
    """Non-technical arts and design roles should be excluded."""
    assert should_keep(JobRecord(company="Design Studio", title="Graphic Design Intern")) is False
    assert should_keep(JobRecord(company="Media Co", title="Photographer Intern")) is False
    assert should_keep(JobRecord(company="Video Co", title="Videographer Intern")) is False
    assert should_keep(JobRecord(company="Gallery", title="Artist Intern")) is False


def test_include_technical_roles():
    """Technical roles should be kept (include list)."""
    assert should_keep(JobRecord(company="Tech Co", title="Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="SWE Intern")) is True
    assert should_keep(JobRecord(company="Big Tech", title="SDE Intern")) is True
    assert should_keep(JobRecord(company="Company", title="Backend Engineer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Frontend Developer Intern")) is True
    assert should_keep(JobRecord(company="Tech", title="Full Stack Engineer Intern")) is True
    assert should_keep(JobRecord(company="AI Co", title="Machine Learning Intern")) is True
    assert should_keep(JobRecord(company="Data Co", title="Data Science Intern")) is True
    assert should_keep(JobRecord(company="Analytics", title="Data Engineer Intern")) is True
    assert should_keep(JobRecord(company="AI Lab", title="Research Intern")) is True
    assert should_keep(JobRecord(company="Finance Tech", title="Quant Intern")) is True
    assert should_keep(JobRecord(company="Cloud Co", title="DevOps Intern")) is True
    assert should_keep(JobRecord(company="Tech", title="Platform Engineer Intern")) is True
    assert should_keep(JobRecord(company="Security", title="Security Engineer Intern")) is True
    assert should_keep(JobRecord(company="Robotics", title="Robotics Intern")) is True
    assert should_keep(JobRecord(company="AI", title="Applied AI Intern")) is True
    assert should_keep(JobRecord(company="ML Co", title="MLE Intern")) is True
    assert should_keep(JobRecord(company="AI Lab", title="Deep Learning Intern")) is True
    assert should_keep(JobRecord(company="NLP Co", title="NLP Engineer Intern")) is True
    assert should_keep(JobRecord(company="Vision Co", title="Computer Vision Intern")) is True


def test_exclude_override_with_strong_include():
    """Exclude matches should be overridden by strong include signals."""
    # Edge case: "tax" appears but "software engineer" is strong signal
    assert should_keep(JobRecord(company="TaxTech", title="Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Finance Co", title="Machine Learning Engineer")) is True
    assert should_keep(JobRecord(company="Nursing Tech", title="Data Science Engineer")) is True
    # True exclude without strong signals
    assert should_keep(JobRecord(company="TaxCorp", title="Tax Accountant Intern")) is False


def test_edge_cases_ambiguous():
    """Ambiguous roles with context-dependent relevance."""
    # "analyst" is in include list, should keep
    assert should_keep(JobRecord(company="Tech Co", title="Data Analyst Intern")) is True
    # "analytics" is in include list
    assert should_keep(JobRecord(company="Startup", title="Analytics Intern")) is True
    # Product roles without technical keywords default to keep (recall-first)
    assert should_keep(JobRecord(company="Tech", title="Product Intern")) is True
    # Unknown roles default to keep (recall-first)
    assert should_keep(JobRecord(company="Unknown Co", title="Mystery Intern")) is True


def test_snippet_context_matters():
    """Snippet text is included in classification blob."""
    # Exclude keyword in snippet
    assert should_keep(JobRecord(
        company="Tech Co", 
        title="Intern",
        snippet="Looking for a nursing background candidate"
    )) is False
    # Include keyword in snippet
    assert should_keep(JobRecord(
        company="Company", 
        title="Intern",
        snippet="Work on machine learning projects"
    )) is True


# --- Original tests preserved below ---


def test_dedupe_fuzzy():
    a = JobRecord(company="OpenAI", title="Software Engineer Intern", location="San Francisco, CA", url="")
    b = JobRecord(company="OpenAI Inc", title="Software Engineer Intern", location="San Francisco CA", url="")
    assert is_duplicate(a, b)


def test_notify_once(tmp_path):
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = MockNotifier(path=path, db=db)
    job = JobRecord(company="Stripe", title="SWE Intern", location="SF", url="https://ex/1", priority=True)
    assert n.notify(job) is True
    assert n.notify(job) is False
    text = format_alert(job)
    assert "[PRIORITY]" in text
    assert path.read_text().count("\n") == 1


def test_pipeline_empty_sources(tmp_path):
    db = Database(tmp_path / "p.db")
    stats = run_scan(db=db, sources=[])
    assert stats.fetched == 0
    assert stats.seed_mode is True
    assert stats.notified == 0


def test_pipeline_seeds_first_scan_then_alerts(tmp_path):
    from jobradar.models import JobRecord
    from jobradar.notify import MockNotifier

    db = Database(tmp_path / "s.db")
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="SF",
        url="https://example.com/stripe-intern",
        sources=["test"],
    )
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is False
    n = MockNotifier(path=tmp_path / "n.jsonl", db=db)
    assert n.notify(stored) is True
    assert n.notify(stored) is False
