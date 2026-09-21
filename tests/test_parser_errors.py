"""Test parser error handling and resilience."""

import json
import logging

import pytest

from jobradar.parsers import (
    parse_aprameyak_json,
    parse_applyguy_json,
    parse_dreamwork_json,
    parse_source,
)


def test_aprameyak_malformed_json(caplog):
    """Malformed JSON returns empty list with error log."""
    malformed = '{"incomplete": '
    
    with caplog.at_level(logging.ERROR):
        result = parse_aprameyak_json(malformed, source="test-aprameyak")
    
    assert result == []
    assert "JSON decode error" in caplog.text
    assert "test-aprameyak" in caplog.text


def test_aprameyak_not_a_list(caplog):
    """JSON object instead of list returns empty with warning."""
    wrong_type = '{"data": "not a list"}'
    
    with caplog.at_level(logging.WARNING):
        result = parse_aprameyak_json(wrong_type, source="test-aprameyak")
    
    assert result == []
    assert "expected list" in caplog.text
    assert "test-aprameyak" in caplog.text


def test_aprameyak_empty_string():
    """Empty string returns empty list."""
    result = parse_aprameyak_json("", source="test-aprameyak")
    assert result == []


def test_aprameyak_null_bytes():
    """Null bytes in JSON are handled."""
    malformed = b'{"company": "Test\x00"}'
    result = parse_aprameyak_json(malformed, source="test-aprameyak")
    assert result == []


def test_aprameyak_truncated_json(caplog):
    """Truncated JSON returns empty list with error."""
    truncated = '[{"company": "OpenAI", "title": "SWE Intern", "url":'
    
    with caplog.at_level(logging.ERROR):
        result = parse_aprameyak_json(truncated, source="test-aprameyak")
    
    assert result == []
    assert "JSON decode error" in caplog.text


def test_aprameyak_valid_recovery():
    """Valid JSON after fixing errors works correctly."""
    valid = json.dumps([
        {"company": "OpenAI", "role": "SWE Intern", "location": "SF", "url": "https://openai.com/job1"}
    ])
    
    result = parse_aprameyak_json(valid, source="test-aprameyak")
    
    assert len(result) == 1
    assert result[0].company == "OpenAI"
    assert result[0].title == "SWE Intern"


def test_dreamwork_malformed_json(caplog):
    """Malformed JSON in dreamwork format returns empty list."""
    malformed = '{"listings": [{"company":'
    
    with caplog.at_level(logging.ERROR):
        result = parse_dreamwork_json(malformed, source="test-dreamwork")
    
    assert result == []
    assert "JSON decode error" in caplog.text
    assert "test-dreamwork" in caplog.text


def test_dreamwork_missing_listings_field(caplog):
    """JSON missing listings field returns empty with warning."""
    wrong_structure = '{"data": []}'
    
    with caplog.at_level(logging.WARNING):
        result = parse_dreamwork_json(wrong_structure, source="test-dreamwork")
    
    assert result == []
    assert "expected listings list" in caplog.text


def test_dreamwork_listings_not_list(caplog):
    """listings field that's not a list returns empty."""
    wrong_type = '{"listings": "not a list"}'
    
    with caplog.at_level(logging.WARNING):
        result = parse_dreamwork_json(wrong_type, source="test-dreamwork")
    
    assert result == []
    assert "expected listings list" in caplog.text


def test_dreamwork_valid_recovery():
    """Valid dreamwork JSON works correctly."""
    valid = json.dumps({
        "listings": [
            {"company": "Databricks", "title": "Data Engineering Intern", "location": "SF", "url": "https://databricks.com/job1"}
        ]
    })
    
    result = parse_dreamwork_json(valid, source="test-dreamwork")
    
    assert len(result) == 1
    assert result[0].company == "Databricks"


def test_applyguy_malformed_json(caplog):
    """Malformed JSON in applyguy format returns empty list."""
    malformed = '{"jobs": [{"company":'
    
    with caplog.at_level(logging.ERROR):
        result = parse_applyguy_json(malformed, source="test-applyguy")
    
    assert result == []
    assert "JSON decode error" in caplog.text


def test_applyguy_missing_jobs_field(caplog):
    """JSON missing jobs field returns empty."""
    wrong_structure = '{"listings": []}'
    
    with caplog.at_level(logging.WARNING):
        result = parse_applyguy_json(wrong_structure, source="test-applyguy")
    
    assert result == []
    assert "expected jobs list" in caplog.text


def test_applyguy_jobs_not_list(caplog):
    """jobs field that's not a list returns empty."""
    wrong_type = '{"jobs": "not a list"}'
    
    with caplog.at_level(logging.WARNING):
        result = parse_applyguy_json(wrong_type, source="test-applyguy")
    
    assert result == []
    assert "expected jobs list" in caplog.text


def test_applyguy_valid_recovery():
    """Valid applyguy JSON works correctly."""
    valid = json.dumps({
        "jobs": [
            {"company": "Stripe", "title": "SWE Intern", "location": "SF", "listingUrl": "https://stripe.com/job1"}
        ]
    })
    
    result = parse_applyguy_json(valid, source="test-applyguy")
    
    assert len(result) == 1
    assert result[0].company == "Stripe"


def test_parse_source_error_isolation():
    """Errors in one parser don't affect parse_source dispatch."""
    # Bad JSON for aprameyak
    result = parse_source("aprameyak", '{"bad":', source_name="test-source")
    assert result == []
    
    # Valid JSON still works
    valid = json.dumps([{"company": "Meta", "role": "SWE", "location": "Menlo", "url": "https://meta.com/j1"}])
    result = parse_source("aprameyak", valid, source_name="test-source")
    assert len(result) == 1


def test_unicode_error_handling(caplog):
    """Unicode errors in malformed JSON are handled."""
    # Invalid UTF-8 sequence
    malformed = b'[{"company": "\xff\xfe invalid utf8"}]'
    
    with caplog.at_level(logging.ERROR):
        result = parse_aprameyak_json(malformed, source="test-unicode")
    
    assert result == []
    assert ("JSON decode error" in caplog.text or "Parse error" in caplog.text)


def test_error_log_includes_preview(caplog):
    """Error logs include preview of malformed data."""
    malformed = '{"very": "long malformed json that goes on and on and on' + 'x' * 200
    
    with caplog.at_level(logging.ERROR):
        result = parse_aprameyak_json(malformed, source="test-preview")
    
    assert result == []
    assert "Preview:" in caplog.text
    # Should be truncated to 100 chars
    assert len(caplog.records[0].getMessage()) < len(malformed)


def test_partial_valid_data_recovered():
    """Parser recovers valid items even if some are malformed."""
    # List with one valid item and one missing required fields
    partial = json.dumps([
        {"company": "OpenAI", "role": "SWE Intern", "url": "https://openai.com/j1"},
        {"company": "", "role": ""},  # Missing required fields
        {"company": "Meta", "role": "Data Intern", "url": "https://meta.com/j1"},
    ])
    
    result = parse_aprameyak_json(partial, source="test-partial")
    
    # Should get 2 valid jobs, skip the malformed one
    assert len(result) == 2
    assert result[0].company == "OpenAI"
    assert result[1].company == "Meta"


def test_empty_json_array():
    """Empty JSON array returns empty list without errors."""
    result = parse_aprameyak_json("[]", source="test-empty")
    assert result == []


def test_json_with_extra_fields():
    """JSON with unexpected extra fields is handled gracefully."""
    extra_fields = json.dumps([{
        "company": "Tesla",
        "role": "AI Intern",
        "url": "https://tesla.com/j1",
        "unexpected_field": "some value",
        "another_extra": 12345,
    }])
    
    result = parse_aprameyak_json(extra_fields, source="test-extra")
    
    assert len(result) == 1
    assert result[0].company == "Tesla"


def test_nested_json_error(caplog):
    """Deeply nested malformed JSON is handled."""
    nested = '{"listings": [{"nested": {"deeply": {"bad":'
    
    with caplog.at_level(logging.ERROR):
        result = parse_dreamwork_json(nested, source="test-nested")
    
    assert result == []
    assert "JSON decode error" in caplog.text
