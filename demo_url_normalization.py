#!/usr/bin/env python3
"""
Demonstration of URL normalization fix for tracking parameter deduplication.

This script shows how the same job posting with different tracking parameters
now generates the same canonical_key, preventing duplicate alerts.
"""

from src.jobradar.models import canonical_key, normalize_url

print("=" * 80)
print("JobRadar URL Normalization Fix - Demonstration")
print("=" * 80)
print()

# Example 1: Hudl Product Management Intern (from bug report)
print("Example 1: Hudl Product Management Intern (Real Bug Scenario)")
print("-" * 80)

company = "Hudl"
title = "Product Management Intern"
location = "Remote"

url_morning = "https://hudl.com/careers/job/123?utm_source=aprameyak"
url_evening = "https://hudl.com/careers/job/123?utm_source=Simplify&ref=Simplify"

print(f"Company: {company}")
print(f"Title: {title}")
print(f"Location: {location}")
print()
print(f"Morning URL:  {url_morning}")
print(f"Evening URL:  {url_evening}")
print()

norm_morning = normalize_url(url_morning)
norm_evening = normalize_url(url_evening)

print(f"Normalized Morning: {norm_morning}")
print(f"Normalized Evening: {norm_evening}")
print(f"Match: {norm_morning == norm_evening} ✓")
print()

key_morning = canonical_key(company, title, location, url_morning)
key_evening = canonical_key(company, title, location, url_evening)

print(f"canonical_key Morning: {key_morning}")
print(f"canonical_key Evening: {key_evening}")
print(f"Match: {key_morning == key_evening} ✓")
print()
print("Result: Same job = Same key = No duplicate alert! 🎉")
print()

# Example 2: Workday URL variants
print("=" * 80)
print("Example 2: Workday URL Variants")
print("-" * 80)

company = "Tech Company"
title = "Software Engineer Intern"
location = "San Francisco, CA"

url1 = "https://myworkdayjobs.com/company/job/Engineer/SWE-Intern_JR12345?source=LinkedIn"
url2 = "https://myworkdayjobs.com/company/job/Engineer/SWE-Intern_JR12345?source=Indeed&ref=external"

print(f"Company: {company}")
print(f"Title: {title}")
print()
print(f"URL 1 (LinkedIn):  {url1}")
print(f"URL 2 (Indeed):    {url2}")
print()

norm1 = normalize_url(url1)
norm2 = normalize_url(url2)

print(f"Normalized 1: {norm1}")
print(f"Normalized 2: {norm2}")
print(f"Match: {norm1 == norm2} ✓")
print()

key1 = canonical_key(company, title, location, url1)
key2 = canonical_key(company, title, location, url2)

print(f"canonical_key 1: {key1}")
print(f"canonical_key 2: {key2}")
print(f"Match: {key1 == key2} ✓")
print()

# Example 3: Greenhouse with job ID preserved
print("=" * 80)
print("Example 3: Greenhouse URL with Job ID Preserved")
print("-" * 80)

url_with_tracking = "https://boards.greenhouse.io/company/jobs/123?gh_jid=456&utm_source=linkedin"
url_clean = "https://boards.greenhouse.io/company/jobs/123?gh_jid=456"

print(f"URL with tracking: {url_with_tracking}")
print(f"URL clean:         {url_clean}")
print()

norm_with_tracking = normalize_url(url_with_tracking)
norm_clean = normalize_url(url_clean)

print(f"Normalized with tracking: {norm_with_tracking}")
print(f"Normalized clean:         {norm_clean}")
print(f"Match: {norm_with_tracking == norm_clean} ✓")
print()
print("Note: gh_jid parameter is preserved (job identifier) ✓")
print()

# Example 4: Different jobs still get different keys
print("=" * 80)
print("Example 4: Different Jobs Still Get Different Keys")
print("-" * 80)

url_job1 = "https://company.com/careers/job/123"
url_job2 = "https://company.com/careers/job/456"

key_job1 = canonical_key("Company", "SWE Intern", "SF", url_job1)
key_job2 = canonical_key("Company", "SWE Intern", "SF", url_job2)

print(f"Job 1 URL: {url_job1}")
print(f"Job 2 URL: {url_job2}")
print()
print(f"canonical_key Job 1: {key_job1}")
print(f"canonical_key Job 2: {key_job2}")
print(f"Different: {key_job1 != key_job2} ✓")
print()

print("=" * 80)
print("Summary")
print("=" * 80)
print("✓ Same job with different tracking params → Same canonical_key")
print("✓ Job-identifying parameters (gh_jid, etc.) → Preserved")
print("✓ Different jobs → Different canonical_keys")
print("✓ No duplicate alerts for tracking parameter changes!")
print("=" * 80)
