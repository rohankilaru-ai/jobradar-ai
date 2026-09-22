from datetime import datetime, timedelta, timezone

from jobradar.classify import is_priority_company, should_keep
from jobradar.db import Database
from jobradar.dedupe import is_duplicate
from jobradar.models import JobRecord
from jobradar.notify import MockNotifier, format_alert, within_notify_window
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


def test_exclude_newgrad_fulltime():
    """New-grad and full-time roles should be excluded unless clearly internships."""
    # Pure new-grad roles (no intern signal) should be excluded
    assert should_keep(JobRecord(company="Tech Co", title="Software Engineer - New Grad")) is False
    assert should_keep(JobRecord(company="Startup", title="New Graduate Software Engineer")) is False
    assert should_keep(JobRecord(company="BigTech", title="SWE - Recent Graduate")) is False
    assert should_keep(JobRecord(company="Company", title="University Graduate - SDE")) is False
    assert should_keep(JobRecord(company="Firm", title="College Graduate Engineer")) is False
    
    # Full-time roles without intern signal should be excluded
    assert should_keep(JobRecord(company="Tech", title="Software Engineer - Full-Time")) is False
    assert should_keep(JobRecord(company="Startup", title="Full Time SWE")) is False
    assert should_keep(JobRecord(company="Company", title="Entry Level Engineer")) is False
    assert should_keep(JobRecord(company="Firm", title="Entry-Level Software Developer")) is False
    
    # Hybrid roles with both new-grad AND intern signals should be kept
    assert should_keep(JobRecord(company="Tech", title="New Grad Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Software Intern - New Graduate")) is True
    assert should_keep(JobRecord(company="Company", title="Summer Intern (Recent Graduates Welcome)")) is True
    
    # Pure intern roles should be kept
    assert should_keep(JobRecord(company="Tech", title="Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Summer SWE Intern")) is True
    assert should_keep(JobRecord(company="Company", title="Co-op Software Engineer")) is True
    assert should_keep(JobRecord(company="Firm", title="Spring Intern - ML Engineer")) is True


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


# --- Overnight #14: Enhanced exclude-list tuning tests ---


def test_exclude_additional_finance_nontechnical():
    """Additional non-technical finance roles (IB, PE, wealth mgmt) should be excluded."""
    assert should_keep(JobRecord(company="Bank", title="Investment Banking Analyst Intern")) is False
    assert should_keep(JobRecord(company="Finance", title="Private Equity Analyst Intern")) is False
    assert should_keep(JobRecord(company="Wealth Co", title="Wealth Management Intern")) is False
    assert should_keep(JobRecord(company="Bank", title="Personal Banker Intern")) is False
    assert should_keep(JobRecord(company="Credit Union", title="Credit Analyst Intern")) is False
    assert should_keep(JobRecord(company="Audit Firm", title="Audit Intern")) is False
    assert should_keep(JobRecord(company="Tax Prep", title="Tax Preparer Intern")) is False
    assert should_keep(JobRecord(company="Finance Corp", title="Financial Advisor Intern")) is False


def test_exclude_consulting_nontechnical():
    """Non-technical management consulting roles should be excluded."""
    assert should_keep(JobRecord(company="Consulting Firm", title="Management Consulting Intern")) is False
    assert should_keep(JobRecord(company="Strategy Co", title="Strategy Consulting Intern")) is False
    assert should_keep(JobRecord(company="Business Consulting", title="Business Consultant Intern")) is False


def test_exclude_construction_trades():
    """Construction, trades, and manual labor roles should be excluded."""
    assert should_keep(JobRecord(company="Construction Co", title="Construction Intern")) is False
    assert should_keep(JobRecord(company="Electric Co", title="Electrician Intern")) is False
    assert should_keep(JobRecord(company="Plumbing Co", title="Plumber Intern")) is False
    assert should_keep(JobRecord(company="Auto Shop", title="Mechanic Intern")) is False
    assert should_keep(JobRecord(company="Facilities", title="Maintenance Intern")) is False
    assert should_keep(JobRecord(company="HVAC Co", title="HVAC Intern")) is False


def test_exclude_insurance():
    """Insurance roles should be excluded."""
    assert should_keep(JobRecord(company="Insurance Co", title="Insurance Intern")) is False
    assert should_keep(JobRecord(company="Claims Co", title="Claims Adjuster Intern")) is False
    assert should_keep(JobRecord(company="Underwriting", title="Underwriter Intern")) is False


def test_exclude_additional_healthcare():
    """Additional healthcare roles (therapist, scribe, patient care) should be excluded."""
    assert should_keep(JobRecord(company="Clinic", title="Physical Therapy Intern")) is False
    assert should_keep(JobRecord(company="Rehab Center", title="Occupational Therapy Intern")) is False
    assert should_keep(JobRecord(company="Hospital", title="Medical Scribe Intern")) is False
    assert should_keep(JobRecord(company="Healthcare", title="Patient Care Intern")) is False
    assert should_keep(JobRecord(company="Pharmacy", title="Pharmacy Tech Intern")) is False
    assert should_keep(JobRecord(company="Mental Health", title="Therapist Intern")) is False


def test_exclude_additional_hr_admin():
    """Additional HR/admin roles (EA, recruiting coordinator) should be excluded."""
    assert should_keep(JobRecord(company="Corp", title="Executive Assistant Intern")) is False
    assert should_keep(JobRecord(company="Office", title="Office Manager Intern")) is False
    assert should_keep(JobRecord(company="Recruiting", title="Recruiting Coordinator Intern")) is False


def test_exclude_additional_sales_marketing():
    """Additional sales/marketing roles (SDR, customer success, growth) should be excluded."""
    assert should_keep(JobRecord(company="Sales Co", title="Sales Development Intern")) is False
    assert should_keep(JobRecord(company="SaaS Co", title="Customer Success Intern")) is False
    assert should_keep(JobRecord(company="Startup", title="Account Manager Intern")) is False
    assert should_keep(JobRecord(company="Marketing", title="Growth Marketing Intern")) is False
    assert should_keep(JobRecord(company="Brand Co", title="Brand Marketing Intern")) is False
    assert should_keep(JobRecord(company="Product Co", title="Product Marketing Intern")) is False
    assert should_keep(JobRecord(company="Partnership", title="Partnership Intern")) is False


def test_exclude_additional_content_media():
    """Additional content/media roles (social media, editor, producer) should be excluded."""
    assert should_keep(JobRecord(company="Media Co", title="Social Media Intern")) is False
    assert should_keep(JobRecord(company="Publishing", title="Editor Intern")) is False
    assert should_keep(JobRecord(company="Production Co", title="Media Producer Intern")) is False
    assert should_keep(JobRecord(company="Creator Co", title="Content Creator Intern")) is False


def test_exclude_additional_operations():
    """Additional non-tech operations roles (program coord, business ops) should be excluded."""
    assert should_keep(JobRecord(company="Ops Co", title="Business Operations Intern")) is False
    assert should_keep(JobRecord(company="Program", title="Program Coordinator Intern")) is False
    assert should_keep(JobRecord(company="Projects", title="Project Coordinator Intern")) is False
    assert should_keep(JobRecord(company="Operations", title="Operations Coordinator Intern")) is False


def test_exclude_additional_design():
    """Additional non-tech design roles (UX/UI without eng) should be excluded."""
    assert should_keep(JobRecord(company="Design Co", title="UX Designer Intern")) is False
    assert should_keep(JobRecord(company="UI Studio", title="UI Designer Intern")) is False
    assert should_keep(JobRecord(company="Visual Design", title="Visual Designer Intern")) is False
    assert should_keep(JobRecord(company="Illustration", title="Illustrator Intern")) is False


def test_exclude_additional_service():
    """Additional service roles (barista, front desk, concierge) should be excluded."""
    assert should_keep(JobRecord(company="Coffee Shop", title="Barista Intern")) is False
    assert should_keep(JobRecord(company="Hotel", title="Front Desk Intern")) is False
    assert should_keep(JobRecord(company="Hotel", title="Concierge Intern")) is False


def test_strong_include_overrides_exclude_edge_cases():
    """Strong technical signals should override exclude matches in edge cases."""
    # Tax + Software Engineer = keep (tax is exclude keyword but software engineer is strong signal)
    assert should_keep(JobRecord(company="TaxTech", title="Tax Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="TurboTax", title="Software Engineer - Tax Products")) is True
    
    # Audit + Data Engineer = keep
    assert should_keep(JobRecord(company="AuditTech", title="Audit Data Engineer Intern")) is True
    
    # Legal + ML Engineer = keep
    assert should_keep(JobRecord(company="LegalTech", title="Legal ML Engineer Intern")) is True
    
    # Healthcare + Data Science = keep
    assert should_keep(JobRecord(company="HealthTech", title="Healthcare Data Scientist Intern")) is True
    
    # Marketing + ML = keep
    assert should_keep(JobRecord(company="MarketingAI", title="Marketing ML Engineer Intern")) is True
    
    # Operations + Platform Engineer = keep
    assert should_keep(JobRecord(company="OpsTech", title="Operations Platform Engineer Intern")) is True
    
    # Finance + Quant = keep
    assert should_keep(JobRecord(company="HedgeFund", title="Finance Quant Intern")) is True


def test_grad_level_hard_drop_phd_only():
    """PhD-only roles should be hard-dropped even with intern signal."""
    assert should_keep(JobRecord(company="Research Lab", title="Research Intern - PhD")) is False
    assert should_keep(JobRecord(company="AI Lab", title="ML Research Intern (PhD only)")) is False
    assert should_keep(JobRecord(company="University", title="Summer Intern - Ph.D. Candidates")) is False
    assert should_keep(JobRecord(company="Tech Co", title="Doctoral Research Intern")) is False
    assert should_keep(JobRecord(company="Lab", title="Postdoc Research Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Intern - MS/PhD")) is False
    assert should_keep(JobRecord(company="Firm", title="Research Intern (PhD/MS)")) is False


def test_grad_level_allow_bs_ms_dual_track():
    """BS/MS dual-track roles should be kept (undergrad-eligible)."""
    assert should_keep(JobRecord(company="Tech Co", title="Software Engineer Intern - BS/MS")) is True
    assert should_keep(JobRecord(company="Startup", title="ML Intern (BS / MS)")) is True
    assert should_keep(JobRecord(company="Company", title="SWE Intern - B.S./M.S.")) is True
    assert should_keep(JobRecord(company="Firm", title="Data Engineer Intern - Bachelor/Master")) is True
    assert should_keep(JobRecord(company="AI Lab", title="Research Intern - Bachelor's/Master's")) is True
    assert should_keep(JobRecord(company="Tech", title="Engineering Intern (Bachelor / Master Candidates)")) is True


def test_grad_level_drop_masters_only():
    """Masters-only roles without PhD but also without BS should be dropped."""
    assert should_keep(JobRecord(company="Research Lab", title="Research Intern - Master's")) is False
    assert should_keep(JobRecord(company="Company", title="ML Intern (MS only)")) is False
    assert should_keep(JobRecord(company="Lab", title="Graduate Student Intern")) is False
    assert should_keep(JobRecord(company="Firm", title="Intern - MS Candidates")) is False


def test_newgrad_only_additional_patterns():
    """Additional new-grad pattern variations should be excluded without intern signal."""
    assert should_keep(JobRecord(company="Tech", title="Software Engineer - Early Career")) is False
    assert should_keep(JobRecord(company="Startup", title="SDE - College Graduate")) is False
    assert should_keep(JobRecord(company="Company", title="ML Engineer - University Grad")) is False
    assert should_keep(JobRecord(company="Firm", title="Data Engineer - Grad Program")) is False


def test_newgrad_plus_intern_keep_additional_patterns():
    """New-grad roles that also have intern signals should be kept."""
    assert should_keep(JobRecord(company="Tech", title="Software Intern - Early Career Program")) is True
    assert should_keep(JobRecord(company="Startup", title="Co-op - Recent Graduates")) is True
    assert should_keep(JobRecord(company="Company", title="Fall Intern (New Grad Track)")) is True
    assert should_keep(JobRecord(company="Firm", title="Winter Internship - Entry Level")) is True


def test_recall_first_unknown_roles():
    """Unknown/ambiguous roles without clear exclude/include signals should default to keep."""
    # Pure unknown roles
    assert should_keep(JobRecord(company="Company", title="Emerging Tech Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Innovation Intern")) is True
    assert should_keep(JobRecord(company="Firm", title="Technology Intern")) is True
    
    # Borderline roles (could be tech or non-tech)
    assert should_keep(JobRecord(company="Corp", title="Product Intern")) is True
    assert should_keep(JobRecord(company="Tech", title="Research Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Technical Intern")) is True


def test_intern_signals_override_newgrad():
    """Intern signals should override new-grad exclusion (but not grad-level exclusion)."""
    # New-grad + intern = keep
    assert should_keep(JobRecord(company="Tech", title="New Grad Software Engineer - Summer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Full-Time Track Co-op")) is True
    
    # But PhD + intern = still drop
    assert should_keep(JobRecord(company="Lab", title="PhD Research Intern - Summer")) is False


# --- Overnight #32: Additional exclude-list tuning tests ---


def test_exclude_additional_healthcare_operations():
    """Additional healthcare operations roles should be excluded."""
    assert should_keep(JobRecord(company="Hospital", title="Clinical Research Coordinator Intern")) is False
    assert should_keep(JobRecord(company="Medical Center", title="Medical Records Intern")) is False
    assert should_keep(JobRecord(company="Healthcare Co", title="Health Services Intern")) is False
    assert should_keep(JobRecord(company="Clinic", title="Clinical Operations Intern")) is False


def test_exclude_additional_finance_operations():
    """Additional finance operations roles should be excluded."""
    assert should_keep(JobRecord(company="Finance Co", title="Treasury Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Finance Operations Intern")) is False
    assert should_keep(JobRecord(company="Bank", title="Financial Planning Intern")) is False
    assert should_keep(JobRecord(company="Investment Co", title="Investment Analyst Intern")) is False
    assert should_keep(JobRecord(company="Finance", title="Portfolio Management Intern")) is False
    assert should_keep(JobRecord(company="Insurance", title="Actuary Intern")) is False


def test_exclude_compliance_risk_governance():
    """Compliance, risk, and governance roles should be excluded."""
    assert should_keep(JobRecord(company="Bank", title="Compliance Analyst Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Regulatory Affairs Intern")) is False
    assert should_keep(JobRecord(company="Finance", title="Risk Management Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Governance Intern")) is False
    assert should_keep(JobRecord(company="Legal", title="Policy Analyst Intern")) is False
    assert should_keep(JobRecord(company="Compliance", title="Legal Research Intern")) is False


def test_exclude_additional_hr_operations():
    """Additional HR operations roles should be excluded."""
    assert should_keep(JobRecord(company="Tech Co", title="Talent Acquisition Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="People Operations Intern")) is False
    assert should_keep(JobRecord(company="HR Dept", title="HR Operations Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Compensation Intern")) is False
    assert should_keep(JobRecord(company="Business", title="Benefits Intern")) is False


def test_exclude_additional_sales_revenue_ops():
    """Additional sales and revenue operations roles should be excluded."""
    assert should_keep(JobRecord(company="Sales Co", title="Inside Sales Intern")) is False
    assert should_keep(JobRecord(company="SaaS Co", title="Sales Operations Intern")) is False
    assert should_keep(JobRecord(company="Tech Co", title="Revenue Operations Intern")) is False
    assert should_keep(JobRecord(company="Marketing", title="Demand Generation Intern")) is False
    assert should_keep(JobRecord(company="Sales", title="Field Marketing Intern")) is False
    assert should_keep(JobRecord(company="Events", title="Event Marketing Intern")) is False


def test_exclude_additional_marketing_digital():
    """Additional digital and content marketing roles should be excluded."""
    assert should_keep(JobRecord(company="Marketing Co", title="Digital Marketing Intern")) is False
    assert should_keep(JobRecord(company="Content Co", title="Content Marketing Intern")) is False
    assert should_keep(JobRecord(company="Email Co", title="Email Marketing Intern")) is False
    assert should_keep(JobRecord(company="Influencer", title="Influencer Marketing Intern")) is False
    assert should_keep(JobRecord(company="Affiliate", title="Affiliate Marketing Intern")) is False
    assert should_keep(JobRecord(company="Channel", title="Channel Marketing Intern")) is False


def test_exclude_product_management_nontechnical():
    """Product management roles without engineering context should be excluded."""
    assert should_keep(JobRecord(company="Tech Co", title="Product Management Intern")) is False
    assert should_keep(JobRecord(company="Startup", title="Product Manager Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Associate Product Manager Intern")) is False
    assert should_keep(JobRecord(company="Product Co", title="Product Operations Intern")) is False
    assert should_keep(JobRecord(company="Strategy", title="Product Strategy Intern")) is False


def test_exclude_business_strategy_consulting():
    """Business strategy and non-technical consulting roles should be excluded."""
    assert should_keep(JobRecord(company="Consulting", title="Business Analyst Intern")) is False
    assert should_keep(JobRecord(company="Strategy Co", title="Business Strategy Intern")) is False
    assert should_keep(JobRecord(company="Corp", title="Strategy Intern")) is False
    assert should_keep(JobRecord(company="Company", title="Corporate Strategy Intern")) is False
    assert should_keep(JobRecord(company="Planning", title="Strategic Planning Intern")) is False


def test_exclude_additional_content_community():
    """Additional content and community roles should be excluded."""
    assert should_keep(JobRecord(company="Social Co", title="Community Manager Intern")) is False
    assert should_keep(JobRecord(company="Media", title="Social Media Manager Intern")) is False
    assert should_keep(JobRecord(company="Content", title="Content Strategist Intern")) is False
    assert should_keep(JobRecord(company="Comms", title="Communications Coordinator Intern")) is False


def test_exclude_additional_operations_facilities():
    """Additional operations and facilities roles should be excluded."""
    assert should_keep(JobRecord(company="Operations", title="Facilities Intern")) is False
    assert should_keep(JobRecord(company="Procurement", title="Procurement Intern")) is False
    assert should_keep(JobRecord(company="Vendor Co", title="Vendor Management Intern")) is False
    assert should_keep(JobRecord(company="Supply Chain", title="Supply Chain Analyst Intern")) is False


def test_exclude_customer_support_technical():
    """Customer support and technical support roles should be excluded."""
    assert should_keep(JobRecord(company="Support Co", title="Customer Support Intern")) is False
    assert should_keep(JobRecord(company="Tech Support", title="Technical Support Intern")) is False
    assert should_keep(JobRecord(company="Customer Co", title="Customer Experience Intern")) is False
    assert should_keep(JobRecord(company="Services", title="Client Services Intern")) is False


def test_exclude_education_curriculum():
    """Education and curriculum roles should be excluded."""
    assert should_keep(JobRecord(company="EdTech", title="Curriculum Intern")) is False
    assert should_keep(JobRecord(company="Education", title="Education Program Intern")) is False


def test_exclude_additional_design_creative():
    """Additional non-technical design and creative roles should be excluded."""
    assert should_keep(JobRecord(company="Design", title="Motion Graphics Intern")) is False
    assert should_keep(JobRecord(company="3D Studio", title="3D Artist Intern")) is False
    assert should_keep(JobRecord(company="Animation", title="Animator Intern")) is False
    assert should_keep(JobRecord(company="Creative", title="Creative Intern")) is False


def test_exclude_additional_facilities_trades():
    """Additional facilities and trades roles should be excluded."""
    assert should_keep(JobRecord(company="Facilities", title="Facilities Technician Intern")) is False


def test_exclude_event_planning():
    """Event planning and coordination roles should be excluded."""
    assert should_keep(JobRecord(company="Events", title="Event Planning Intern")) is False
    assert should_keep(JobRecord(company="Conference", title="Event Coordinator Intern")) is False
    assert should_keep(JobRecord(company="Events Co", title="Conference Coordinator Intern")) is False


def test_exclude_sustainability_nontechnical():
    """Non-technical sustainability roles should be excluded."""
    assert should_keep(JobRecord(company="Green Co", title="Sustainability Intern")) is False
    assert should_keep(JobRecord(company="ESG Corp", title="ESG Intern")) is False
    assert should_keep(JobRecord(company="Environmental", title="Environmental Intern")) is False


def test_strong_override_product_engineer():
    """Product Engineer roles should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="Tech Co", title="Product Engineer Intern")) is True
    assert should_keep(JobRecord(company="Startup", title="Product Infrastructure Engineer")) is True


def test_strong_override_business_intelligence_engineer():
    """Business Intelligence Engineer should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="Data Co", title="Business Intelligence Engineer Intern")) is True
    assert should_keep(JobRecord(company="Analytics", title="BI Engineer Intern")) is True


def test_strong_override_marketing_data_science():
    """Marketing Data Science roles should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="MarketingAI", title="Marketing Data Scientist Intern")) is True
    assert should_keep(JobRecord(company="AdTech", title="Marketing Data Engineer")) is True


def test_strong_override_operations_software_engineer():
    """Operations Software Engineer should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="OpsTech", title="Operations Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="RevOps", title="Revenue Operations Platform Engineer")) is True


def test_strong_override_sustainability_data_engineer():
    """Sustainability Data Engineer should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="GreenTech", title="Sustainability Data Engineer Intern")) is True
    assert should_keep(JobRecord(company="Climate", title="Environmental ML Engineer")) is True


def test_strong_override_compliance_software_engineer():
    """Compliance Software Engineer should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="RegTech", title="Compliance Software Engineer Intern")) is True
    assert should_keep(JobRecord(company="FinTech", title="Risk ML Engineer")) is True


def test_strong_override_customer_data_engineer():
    """Customer Data Engineer should be kept (strong technical signal)."""
    assert should_keep(JobRecord(company="CustomerTech", title="Customer Data Engineer Intern")) is True
    assert should_keep(JobRecord(company="CX Tech", title="Customer Analytics Engineer")) is True


# --- Overnight #39: Classification recall for borderline technical roles ---


def test_borderline_technical_account_manager():
    """Technical Account Manager should be kept (borderline technical role)."""
    # Technical variant should be kept
    assert should_keep(JobRecord(company="Tech Co", title="Technical Account Manager Intern")) is True
    assert should_keep(JobRecord(company="SaaS Co", title="Technical Account Manager")) is True
    assert should_keep(JobRecord(company="Cloud Co", title="TAM Intern - Technical Account Manager")) is True
    # Regular Account Manager should still be excluded
    assert should_keep(JobRecord(company="Sales Co", title="Account Manager Intern")) is False


def test_borderline_technical_product_manager():
    """Technical Product Manager should be kept (borderline technical role)."""
    # Technical variant should be kept
    assert should_keep(JobRecord(company="Tech Co", title="Technical Product Manager Intern")) is True
    assert should_keep(JobRecord(company="SaaS Co", title="Technical Product Manager")) is True
    assert should_keep(JobRecord(company="AI Co", title="TPM - Technical Product Manager Intern")) is True
    # Regular Product Manager should still be excluded
    assert should_keep(JobRecord(company="Product Co", title="Product Manager Intern")) is False
    # Product Marketing should still be excluded
    assert should_keep(JobRecord(company="Marketing", title="Product Marketing Intern")) is False


def test_borderline_solutions_engineer():
    """Solutions Engineer and related roles should be kept."""
    assert should_keep(JobRecord(company="Tech Co", title="Solutions Engineer Intern")) is True
    assert should_keep(JobRecord(company="SaaS Co", title="Technical Solutions Engineer Intern")) is True
    assert should_keep(JobRecord(company="Cloud", title="Customer Solutions Engineer")) is True
    assert should_keep(JobRecord(company="Platform", title="Solutions Architect Intern")) is True


def test_borderline_field_application_engineer():
    """Field and Application Engineers should be kept."""
    assert should_keep(JobRecord(company="Hardware Co", title="Field Application Engineer Intern")) is True
    assert should_keep(JobRecord(company="Chip Co", title="Field Engineer Intern")) is True
    assert should_keep(JobRecord(company="Tech", title="Application Engineer Intern")) is True


def test_borderline_implementation_support_engineer():
    """Implementation and Support Engineers should be kept (technical roles)."""
    assert should_keep(JobRecord(company="SaaS Co", title="Implementation Engineer Intern")) is True
    assert should_keep(JobRecord(company="Platform", title="Support Engineer Intern")) is True
    assert should_keep(JobRecord(company="Cloud", title="Customer Engineer Intern")) is True
    # But Technical Support without 'Engineer' should stay excluded
    assert should_keep(JobRecord(company="Support", title="Technical Support Intern")) is False


def test_borderline_integration_professional_services():
    """Integration and Professional Services Engineers should be kept."""
    assert should_keep(JobRecord(company="Integration Co", title="Integration Engineer Intern")) is True
    assert should_keep(JobRecord(company="Consulting", title="Professional Services Engineer Intern")) is True


def test_borderline_architect_roles():
    """Architect roles (solutions, cloud, data, technical) should be kept."""
    assert should_keep(JobRecord(company="Cloud Co", title="Cloud Architect Intern")) is True
    assert should_keep(JobRecord(company="Data Co", title="Data Architect Intern")) is True
    assert should_keep(JobRecord(company="Tech", title="Technical Architect Intern")) is True
    assert should_keep(JobRecord(company="Solutions", title="Solutions Architect Intern")) is True


def test_borderline_technical_program_manager():
    """Technical Program Manager and TPM should be kept."""
    assert should_keep(JobRecord(company="Tech Co", title="Technical Program Manager Intern")) is True
    assert should_keep(JobRecord(company="Platform", title="TPM Intern")) is True
    assert should_keep(JobRecord(company="Infrastructure", title="Technical Project Manager Intern")) is True


def test_borderline_developer_relations():
    """Developer Relations and Developer Advocate roles should be kept."""
    assert should_keep(JobRecord(company="DevTools Co", title="Developer Relations Intern")) is True
    assert should_keep(JobRecord(company="API Co", title="Developer Advocate Intern")) is True
    assert should_keep(JobRecord(company="Platform", title="DevRel Engineer Intern")) is True


def test_borderline_site_reliability_engineer():
    """Site Reliability Engineer (SRE) should be kept."""
    assert should_keep(JobRecord(company="Cloud Co", title="Site Reliability Engineer Intern")) is True
    assert should_keep(JobRecord(company="Platform", title="SRE Intern")) is True


def test_borderline_edge_cases_summary():
    """Summary test: all borderline technical roles should be kept."""
    borderline_keep = [
        "Product Engineer Intern",
        "Technical Account Manager Intern",
        "Technical Product Manager Intern",
        "Solutions Engineer Intern",
        "Technical Solutions Engineer Intern",
        "Customer Engineer Intern",
        "Field Application Engineer Intern",
        "Implementation Engineer Intern",
        "Support Engineer Intern",
        "Professional Services Engineer Intern",
        "Integration Engineer Intern",
        "Site Reliability Engineer Intern",
        "Solutions Architect Intern",
        "Cloud Architect Intern",
        "Technical Program Manager Intern",
        "Developer Relations Intern",
    ]
    
    for title in borderline_keep:
        assert should_keep(JobRecord(company="TechCo", title=title)) is True, \
            f"Borderline technical role should be kept: {title}"


# --- Original tests preserved below ---


def test_dedupe_fuzzy():
    a = JobRecord(company="OpenAI", title="Software Engineer Intern", location="San Francisco, CA", url="")
    b = JobRecord(company="OpenAI Inc", title="Software Engineer Intern", location="San Francisco CA", url="")
    assert is_duplicate(a, b)


def test_notify_once(tmp_path):
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = MockNotifier(path=path, db=db)
    job = JobRecord(company="Stripe", title="SWE Intern", location="SF", url="https://stripe.com/jobs/1", priority=True)
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
        url="https://stripe.com/careers/intern",
        sources=["test"],
    )
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is False
    n = MockNotifier(path=tmp_path / "n.jsonl", db=db)
    assert n.notify(stored) is True
    assert n.notify(stored) is False


def test_within_notify_window_3_days():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    fresh = JobRecord(
        company="A",
        title="SWE Intern",
        url="https://ex/fresh",
        first_seen_at=(now - timedelta(days=2)).isoformat(),
    )
    stale = JobRecord(
        company="B",
        title="SWE Intern",
        url="https://ex/stale",
        first_seen_at=(now - timedelta(days=16)).isoformat(),
    )
    assert within_notify_window(fresh, now=now) is True
    assert within_notify_window(stale, now=now) is False
    # 3 days old is well within default 14-day window
    edge = JobRecord(
        company="C",
        title="SWE Intern",
        url="https://ex/edge",
        first_seen_at=(now - timedelta(days=3)).isoformat(),
    )
    assert within_notify_window(edge, now=now) is True


def test_pipeline_stores_old_jobs_without_notify(tmp_path, monkeypatch):
    """Older-than-window jobs are persisted but never alerted."""
    from jobradar.scout import ScoutResult
    from jobradar import pipeline as pipeline_mod

    db = Database(tmp_path / "old.db")
    # Pre-seed so we are not in seed_mode
    db.upsert_job(
        JobRecord(company="Seed", title="SWE Intern", location="SF", url="https://seed.com/jobs", sources=["seed"])
    )
    now = datetime.now(timezone.utc)
    old = JobRecord(
        company="Jane Street",
        title="Software Engineer Intern",
        location="NYC",
        url="https://janestreet.com/join/position/abc",
        sources=["test"],
        first_seen_at=(now - timedelta(days=30)).isoformat(),
    )
    fresh = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="SF",
        url="https://stripe.com/jobs/listing/swe-intern",
        sources=["test"],
        first_seen_at=now.isoformat(),
    )

    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=[old, fresh], not_modified=False, error=None)]

    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notifications.jsonl"))
    stats = run_scan(db=db, sources=[])
    assert db.get_job(old.canonical_key) is not None
    assert db.get_job(fresh.canonical_key) is not None
    assert stats.new == 2
    assert stats.notified == 1
    assert db.was_notified(fresh.canonical_key) is True
    assert db.was_notified(old.canonical_key) is False


def test_pipeline_no_duplicate_alert_on_tracking_param_change(tmp_path, monkeypatch):
    """Same job with different tracking params should not trigger duplicate alert."""
    from jobradar.scout import ScoutResult
    from jobradar import pipeline as pipeline_mod

    db = Database(tmp_path / "tracking.db")
    notify_path = tmp_path / "notifications.jsonl"
    
    # Pre-seed so we are not in seed_mode
    db.upsert_job(
        JobRecord(company="Seed", title="SWE Intern", location="SF", 
                 url="https://seed.com/jobs", sources=["seed"])
    )
    
    now = datetime.now(timezone.utc)
    
    # Morning scan: Job with utm_source=aprameyak
    morning_job = JobRecord(
        company="Hudl",
        title="Software Engineer Intern",
        location="Remote",
        url="https://hudl.com/careers/job/123?utm_source=aprameyak",
        sources=["simplify"],
        first_seen_at=now.isoformat(),
    )
    
    def morning_scout(db_arg, sources=None):
        return [ScoutResult(source="simplify", jobs=[morning_job], not_modified=False, error=None)]
    
    monkeypatch.setattr(pipeline_mod, "scout_all", morning_scout)
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(notify_path))
    
    # First scan: should notify
    stats1 = run_scan(db=db, sources=[])
    assert stats1.new == 1
    assert stats1.notified == 1
    assert db.was_notified(morning_job.canonical_key) is True
    
    # Evening scan: Same job but with utm_source=Simplify&ref=Simplify
    evening_job = JobRecord(
        company="Hudl",
        title="Software Engineer Intern",
        location="Remote",
        url="https://hudl.com/careers/job/123?utm_source=Simplify&ref=Simplify",
        sources=["simplify"],
        first_seen_at=now.isoformat(),
    )
    
    def evening_scout(db_arg, sources=None):
        return [ScoutResult(source="simplify", jobs=[evening_job], not_modified=False, error=None)]
    
    monkeypatch.setattr(pipeline_mod, "scout_all", evening_scout)
    
    # Second scan: should NOT notify (same job, just different tracking params)
    stats2 = run_scan(db=db, sources=[])
    
    # Key assertions: canonical_key should be the same despite different URLs
    assert morning_job.canonical_key == evening_job.canonical_key, \
        f"canonical_key mismatch: {morning_job.canonical_key} != {evening_job.canonical_key}"
    
    # Should be recognized as duplicate (not new)
    assert stats2.new == 0, f"Expected 0 new jobs, got {stats2.new}"
    assert stats2.notified == 0, f"Expected 0 notifications, got {stats2.notified}"
    
    # Notification count should still be 1 (from morning scan only)
    notification_lines = notify_path.read_text().strip().split("\n") if notify_path.exists() else []
    assert len(notification_lines) == 1, f"Expected 1 notification, got {len(notification_lines)}"
