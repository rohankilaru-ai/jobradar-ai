from jobradar.gmail import classify_email, extract_company_guess


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
