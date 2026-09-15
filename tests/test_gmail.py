from jobradar.gmail import (
    classify_email,
    classify_role_family,
    extract_company_guess,
    extract_role_guess,
    nested_label_name,
)


def test_classify_applied():
    assert classify_email("Thanks for applying to Stripe") == "applied"


def test_classify_oa():
    assert classify_email("Your HackerRank test for OpenAI") == "oa"


def test_classify_reject():
    assert classify_email("Unfortunately we will not be moving forward") == "rejected"


def test_classify_other():
    assert classify_email("Lunch menu") == "other"


def test_company_guess_from_host():
    assert "stripe" in extract_company_guess("Hello", "jobs@stripe.com").lower()


def test_company_guess_from_subject_doordash():
    company = extract_company_guess(
        "Thank you for applying to DoorDash",
        "no-reply@doordash.com",
        "We've received your application",
    )
    assert "doordash" in company.lower()


def test_company_guess_not_workday_vendor():
    company = extract_company_guess(
        "Thank You for Applying",
        "wexinc@myworkday.com",
        "We've received your information for the position of Fullstack Software Engineer Intern",
    )
    assert "workday" not in company.lower()
    assert "wex" in company.lower()


def test_company_guess_scale_from_greenhouse_subject():
    company = extract_company_guess(
        "Thank you for applying to Scale AI",
        "noreply@mail.greenhouse.io",
        "Thanks for applying",
    )
    assert "scale" in company.lower()


def test_role_guess_from_snippet():
    role = extract_role_guess(
        "Thank You for Applying",
        "position of Fullstack Software Engineer Intern (Undergraduate) Our Recruiting Team",
    )
    assert "fullstack" in role.lower() or "software" in role.lower()


def test_role_family_ds():
    assert classify_role_family("Summer 2027 Data Science Intern") == "DS"


def test_nested_label_name():
    assert nested_label_name("Applied") == "JobRadar/Applied"
