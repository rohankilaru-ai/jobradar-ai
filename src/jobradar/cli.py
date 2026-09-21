"""JobRadar CLI entrypoints."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger("jobradar.cli")

from jobradar import __version__
from jobradar.db import Database
from jobradar.director import ping_configured
from jobradar.models import is_bad_url
from jobradar.notify import (
    discord_configured,
    ntfy_configured,
    send_discord,
    send_ntfy,
    send_telegram,
    telegram_configured,
)
from jobradar.pipeline import refresh_jobs, run_scan

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()


def cmd_health(_: argparse.Namespace) -> int:
    from jobradar.notify import alerts_enabled, max_alerts_per_scan, require_posted_at
    
    db = Database()
    channels = ["jsonl"]
    if discord_configured():
        channels.append("discord")
    if ntfy_configured():
        channels.append("ntfy")
    if telegram_configured():
        channels.append("telegram")
    print(f"jobradar {__version__} ok")
    print(f"db: {db.path} ({db.count_jobs()} jobs, {db.count_applications()} applications)")
    print("notifiers: " + " + ".join(channels))
    
    # Alert gates status
    alert_status = "enabled" if alerts_enabled() else "PAUSED"
    max_cap = max_alerts_per_scan()
    cap_str = f"cap={max_cap}" if max_cap > 0 else "unlimited"
    require_date = "require_posted_at" if require_posted_at() else "allow_undated"
    print(f"alerts: {alert_status} ({cap_str}, {require_date})")
    
    from jobradar import gmail as gmail_mod
    from jobradar import notion as notion_mod
    from jobradar.notify import (
        alerts_enabled,
        max_alerts_per_scan,
        require_posted_at,
        NOTIFY_WINDOW_DAYS,
    )
    from jobradar.link_probe import is_placeholder_url

    print("notion: configured" if notion_mod.configured() else "notion: skipped until keys set")
    print("gmail: configured" if gmail_mod.configured() else "gmail: skipped until secrets/gmail-client.json")
    grok_on = any(
        os.environ.get(k)
        for k in ("GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_WEBHOOK_RESUME_MAPPER")
    )
    print("grok webhooks: configured" if grok_on else "grok webhooks: skipped until keys set")
    print(f"director: {'configured' if ping_configured() else 'skipped until keys set'}")
    
    # Runtime gates (overnight #17)
    print(f"\nRuntime gates:")
    print(f"  notify window: {os.environ.get('JOBRADAR_NOTIFY_WINDOW_DAYS', NOTIFY_WINDOW_DAYS)} days")
    print(f"  link probe: {'enabled' if os.environ.get('JOBRADAR_LINK_PROBE', '1').strip() != '0' else 'disabled'}")
    print(f"  alerts: {'enabled' if alerts_enabled() else 'paused'}")
    print(f"  require posted_at: {'yes' if require_posted_at() else 'no'}")
    max_alerts = max_alerts_per_scan()
    print(f"  max alerts/scan: {max_alerts if max_alerts > 0 else 'unlimited'}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    def once() -> None:
        stats = run_scan(alert_all=args.alert_all)
        if stats.seed_mode:
            print(
                f"first scan seeded={stats.seeded} jobs (no alerts). "
                "next scan will notify only new listings."
            )
        print(
            f"scan done fetched={stats.fetched} kept={stats.kept} "
            f"new={stats.new} notified={stats.notified} alerted={stats.alerted} "
            f"probe_deferred={stats.probe_deferred}"
        )
        
        # Per-source breakdown
        if stats.sources:
            print(
                f"sources: ok={stats.sources_ok} not_modified={stats.sources_not_modified} "
                f"failed={stats.sources_failed}"
            )
            for src in stats.sources:
                if src.status == "ok":
                    print(f"  {src.name}: {src.job_count} jobs")
                elif src.status == "not_modified":
                    print(f"  {src.name}: not_modified (304)")
                else:  # error
                    print(f"  {src.name}: error ({src.error_detail})")
        
        if stats.alert_cap_hit:
            print(
                "alert_cap_hit: more new jobs existed but JOBRADAR_MAX_ALERTS_PER_SCAN "
                "stopped further Discord/ntfy this run"
            )
        if stats.source_errors:
            for err in stats.source_errors:
                print(f"source_error: {err}")

    if args.loop:
        interval = args.interval
        print(f"scan loop interval={interval}s")
        try:
            while True:
                once()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("stopped")
            return 0
    once()
    return 0


def cmd_ping_grok(_: argparse.Namespace) -> int:
    for line in ping_configured():
        print(line)
    return 0


def cmd_test_discord(_: argparse.Namespace) -> int:
    if not discord_configured():
        print(
            "skipped (no DISCORD_WEBHOOK_URL / _PRIORITY / _FORTUNE500 / _OTHER). "
            "See docs/ACCOUNTS.md and docs/CLOUD_SCAN.md"
        )
        return 0
    send_discord("JobRadar test — Discord is wired.")
    print("ok")
    return 0


def cmd_test_ntfy(_: argparse.Namespace) -> int:
    if not ntfy_configured():
        print("skipped (no NTFY_TOPIC). See docs/ACCOUNTS.md")
        return 0
    send_ntfy("JobRadar test — ntfy phone push is wired.", title="JobRadar test")
    print("ok")
    return 0


def cmd_test_telegram(_: argparse.Namespace) -> int:
    if not telegram_configured():
        print("skipped (no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). See docs/ACCOUNTS.md")
        return 0
    send_telegram("JobRadar test — Telegram is wired.")
    print("ok")
    return 0


def cmd_test_notion(_: argparse.Namespace) -> int:
    from jobradar import notion as notion_mod

    try:
        print(notion_mod.test_connection())
        return 0
    except Exception as exc:
        print(f"error: {exc}")
        return 1


def cmd_notion_backfill(args: argparse.Namespace) -> int:
    from jobradar import notion as notion_mod

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    n = notion_mod.backfill(db, priority_only=args.priority_only, limit=args.limit, status=args.status)
    print(f"notion upserted={n}")
    return 0


def cmd_gmail_auth(_: argparse.Namespace) -> int:
    from jobradar import gmail as gmail_mod

    try:
        print(gmail_mod.auth())
        return 0
    except Exception as exc:
        print(f"error: {exc}")
        print("See docs/ACCOUNTS.md")
        return 1


def cmd_gmail_sync(args: argparse.Namespace) -> int:
    from jobradar import gmail as gmail_mod

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    stats = gmail_mod.sync(db, days=args.days, max_results=args.max)
    print(stats)
    return 0


def cmd_weekly_report(args: argparse.Namespace) -> int:
    from jobradar.weekly import write_report

    db = Database()
    path = write_report(db=db)
    print(f"ok {path}")
    return 0


def cmd_gmail_reorganize(args: argparse.Namespace) -> int:
    from jobradar import gmail as gmail_mod

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    stats = gmail_mod.reorganize(
        db,
        days=args.days,
        max_threads=args.max_threads,
        dry_run=args.dry_run,
    )
    print(stats)
    return 0


def cmd_verify_links(args: argparse.Namespace) -> int:
    """Probe job URLs from DB or --urls (optional silent --mark-bad quarantine)."""
    from jobradar.link_probe import probe_url

    logging.basicConfig(level=logging.INFO if getattr(args, "verbose", False) else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    # Force probe ON for CLI self-check unless explicitly disabled
    if os.environ.get("JOBRADAR_LINK_PROBE", "1").strip() == "0":
        # still allow explicit probe via link_probe module (CLI always probes)
        pass
    db = Database()

    urls_to_check: list[tuple[str, str]] = []
    if getattr(args, "urls", None):
        for url in args.urls:
            urls_to_check.append((url, url))
    else:
        jobs = db.list_jobs(priority_only=args.priority_only, limit=args.limit)
        for job in jobs:
            urls_to_check.append((job.canonical_key, job.url))

    checked = good = bad = error = 0
    for key, url in urls_to_check:
        checked += 1
        result = probe_url(url)
        if result == "good":
            good += 1
            if args.verbose:
                print(f"✓ good: {url}")
        elif result == "bad":
            bad += 1
            if args.verbose or args.mark_bad:
                print(f"✗ bad: {url}")
            if args.mark_bad and not getattr(args, "urls", None):
                db.upsert_job_closed(key)
        else:
            error += 1
            if args.verbose:
                print(f"? error: {url}")

    print(f"\nverify-links summary: checked={checked} good={good} bad={bad} error={error}")
    if args.mark_bad and not getattr(args, "urls", None):
        print(f"marked {bad} jobs as closed (silent, no alerts)")
    return 0


def cmd_refresh_jobs(_: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    stats = refresh_jobs(db=db)
    print(
        f"refresh done scanned={stats.scanned} matched={stats.matched} "
        f"rewritten={stats.rewritten} skipped={stats.skipped}"
    )
    
    # Per-source breakdown
    if stats.sources:
        print(
            f"sources: ok={stats.sources_ok} not_modified={stats.sources_not_modified} "
            f"failed={stats.sources_failed}"
        )
        for src in stats.sources:
            if src.status == "ok":
                print(f"  {src.name}: {src.job_count} jobs")
            elif src.status == "not_modified":
                print(f"  {src.name}: not_modified (304)")
            else:  # error
                print(f"  {src.name}: error ({src.error_detail})")
    
    if stats.source_errors:
        for err in stats.source_errors:
            print(f"source_error: {err}")
    return 0


def cmd_db_init(_: argparse.Namespace) -> int:
    """Initialize empty DB schema. Use scripts/fresh_db_backup.sh for safe resets."""
    db = Database()
    print(f"db initialized: {db.path}")
    return 0


def cmd_db_refresh(args: argparse.Namespace) -> int:
    """Safe DB refresh: backup existing DB, then recreate empty schema."""
    import shutil
    from datetime import datetime, timezone

    db_path = Path(os.environ.get("JOBRADAR_DB_PATH", "data/jobradar.db"))

    if not db_path.exists():
        print(f"error: no DB at {db_path}")
        return 1

    if args.no_backup:
        print("warning: --no-backup skips safety copy (testing only)")
        confirm = input("type YES to wipe DB without backup: ")
        if confirm != "YES":
            print("aborted")
            return 1
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"{db_path}.backup_{timestamp}")
        print(f"backing up: {db_path} → {backup_path}")
        shutil.copy(db_path, backup_path)
        print(f"backup saved: {backup_path}")

    print(f"removing: {db_path}")
    db_path.unlink()

    print("recreating empty schema...")
    db = Database(db_path)
    print(f"db refresh complete: {db.path} ({db.count_jobs()} jobs)")
    if not args.no_backup:
        print(f"restore with: cp {backup_path} {db_path}")
    return 0


def cmd_quarantine_bad_urls(args: argparse.Namespace) -> int:
    import httpx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    probe_enabled = os.environ.get("JOBRADAR_LINK_PROBE", "0") == "1"

    all_jobs = db.list_jobs(limit=None)
    checked = 0
    quarantined = 0
    already_ok = 0
    errors = 0

    for job in all_jobs:
        checked += 1
        if job.is_closed:
            already_ok += 1
            continue

        quarantine = False
        if is_bad_url(job.url):
            quarantine = True
        elif probe_enabled and job.url:
            try:
                resp = httpx.head(job.url, timeout=5.0, follow_redirects=True)
                if resp.status_code >= 400:
                    quarantine = True
            except Exception as exc:
                log.debug("probe failed for %s: %s", job.url, exc)
                errors += 1

        if quarantine:
            job.is_closed = True
            db.upsert_job(job)
            quarantined += 1
            log.info("quarantined: %s | %s", job.company, job.title)
        else:
            already_ok += 1

    print(f"quarantine scan complete")
    print(f"checked={checked} quarantined={quarantined} already_ok={already_ok} errors={errors}")
    return 0


def cmd_validate_scan(_: argparse.Namespace) -> int:
    """Comprehensive scan validation harness (non-destructive)."""
    print("JobRadar Scan Validation")
    print("=" * 50)
    print()

    # Disable link probe for validation tests (offline mode)
    os.environ["JOBRADAR_LINK_PROBE"] = "0"

    passed = 0
    failed = 0

    # Test 1: Health check
    try:
        channels = ["jsonl"]
        if discord_configured():
            channels.append("discord")
        if ntfy_configured():
            channels.append("ntfy")
        if telegram_configured():
            channels.append("telegram")
        print("✓ Environment health check passed")
        print(f"  Notifiers: {' + '.join(channels)}")
        passed += 1
    except Exception as exc:
        print(f"✗ Environment health check failed: {exc}")
        failed += 1

    print()

    # Test 2: Classification logic
    from jobradar.classify import should_keep
    from jobradar.models import JobRecord

    classification_tests = [
        (JobRecord(company="OpenAI", title="Software Engineer Intern", url="https://openai.com/1"), True, "SWE intern"),
        (JobRecord(company="Hospital", title="Nursing Intern", url="https://hosp.com/1"), False, "nursing intern"),
        (JobRecord(company="Startup", title="Intern", url="https://startup.com/1"), True, "unknown role (recall-first)"),
    ]
    classification_passed = 0
    classification_failed = 0
    for job, expected, desc in classification_tests:
        result = should_keep(job)
        if result == expected:
            classification_passed += 1
        else:
            classification_failed += 1
            print(f"  ✗ Classification failed for {desc}: expected={expected}, got={result}")

    if classification_failed == 0:
        print(f"✓ Classification logic validated ({classification_passed}/{len(classification_tests)} tests passed)")
        passed += 1
    else:
        print(f"✗ Classification logic failed ({classification_failed}/{len(classification_tests)} tests failed)")
        failed += 1

    print()

    # Test 3: Link probe gates
    from jobradar.notify import is_placeholder_url, is_specific_job_url, domain_matches_company

    link_tests = [
        ("is_placeholder_url", "", True, "empty string"),
        ("is_placeholder_url", "TBD", True, "TBD placeholder"),
        ("is_placeholder_url", "https://example.com/job", False, "valid URL"),
        ("is_specific_job_url", "https://stripe.com/careers", False, "generic career page"),
        ("is_specific_job_url", "https://stripe.com/careers/job/1234", True, "specific job page"),
    ]
    link_passed = 0
    link_failed = 0
    for func_name, *test_args in link_tests:
        arg, expected, desc = test_args
        if func_name == "is_placeholder_url":
            result = is_placeholder_url(arg)
        elif func_name == "is_specific_job_url":
            result = is_specific_job_url(arg)
        
        if result == expected:
            link_passed += 1
        else:
            link_failed += 1
            print(f"  ✗ {func_name} failed for {desc}: expected={expected}, got={result}")

    if link_failed == 0:
        print(f"✓ Link probe gates validated ({link_passed}/{len(link_tests)} tests passed)")
        passed += 1
    else:
        print(f"✗ Link probe gates failed ({link_failed}/{len(link_tests)} tests failed)")
        failed += 1

    print()

    # Test 4: Quality gates (domain mismatch, HTML tags) — probe disabled for validation
    from jobradar.notify import job_notify_block_reason

    quality_tests = [
        (JobRecord(company="Google", title="SWE", url="https://google.com/jobs/1"), None, "valid job (probe disabled)"),
        (JobRecord(company="Google", title="SWE", url="https://microsoft.com/jobs/1"), "domain mismatch", "cross-wired company/URL"),
        (JobRecord(company="<div>Stripe</div>", title="SWE", url="https://stripe.com/1"), "HTML in company", "HTML in company"),
        (JobRecord(company="Stripe", title="SWE<br>Intern", url="https://stripe.com/1"), "HTML in title", "HTML in title"),
    ]
    quality_passed = 0
    quality_failed = 0
    for job, expected_substr, desc in quality_tests:
        result = job_notify_block_reason(job)
        if expected_substr is None:
            if result is None:
                quality_passed += 1
            else:
                quality_failed += 1
                print(f"  ✗ Quality gate failed for {desc}: expected no block, got '{result}'")
        else:
            if result and expected_substr in result:
                quality_passed += 1
            else:
                quality_failed += 1
                print(f"  ✗ Quality gate failed for {desc}: expected '{expected_substr}' in block reason, got '{result}'")

    if quality_failed == 0:
        print(f"✓ Quality gates validated ({quality_passed}/{len(quality_tests)} tests passed)")
        passed += 1
    else:
        print(f"✗ Quality gates failed ({quality_failed}/{len(quality_tests)} tests failed)")
        failed += 1

    print()

    # Test 5: Notify window logic
    from jobradar.notify import within_notify_window
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    notify_tests = [
        (JobRecord(company="A", title="X", url="https://a.com/1", posted_at=(now - timedelta(days=1)).date().isoformat()), True, "posted 1 day ago"),
        (JobRecord(company="B", title="Y", url="https://b.com/2", posted_at=(now - timedelta(days=20)).date().isoformat()), False, "posted 20 days ago (outside 14-day window)"),
        (JobRecord(company="C", title="Z", url="https://c.com/3"), False, "no posted_at (REQUIRE_POSTED_AT=1 default)"),
    ]
    notify_passed = 0
    notify_failed = 0
    for job, expected, desc in notify_tests:
        result = within_notify_window(job, now=now)
        if result == expected:
            notify_passed += 1
        else:
            notify_failed += 1
            print(f"  ✗ Notify window failed for {desc}: expected={expected}, got={result}")

    if notify_failed == 0:
        print(f"✓ Notify window logic validated ({notify_passed}/{len(notify_tests)} tests passed)")
        passed += 1
    else:
        print(f"✗ Notify window logic failed ({notify_failed}/{len(notify_tests)} tests failed)")
        failed += 1

    print()

    # Test 6: Database operations (use temporary DB file)
    db_tests_passed = 0
    db_tests_failed = 0
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
            db = Database(tmp.name)
            
            job = JobRecord(company="Meta", title="SWE", url="https://meta.com/1", sources=["test"])
            stored1, is_new1 = db.upsert_job(job)
            stored2, is_new2 = db.upsert_job(job)
            
            if is_new1 and not is_new2 and stored1.canonical_key == stored2.canonical_key:
                db_tests_passed += 1
            else:
                db_tests_failed += 1
                print(f"  ✗ DB upsert idempotence failed")
            
            count = db.count_jobs()
            if count == 1:
                db_tests_passed += 1
            else:
                db_tests_failed += 1
                print(f"  ✗ DB count failed: expected 1, got {count}")
            
            if db_tests_failed == 0:
                print(f"✓ Database operations validated ({db_tests_passed}/2 tests passed)")
                passed += 1
            else:
                print(f"✗ Database operations failed ({db_tests_failed}/2 tests failed)")
                failed += 1
    except Exception as exc:
        print(f"✗ Database operations failed: {exc}")
        failed += 1

    print()
    print("=" * 50)
    if failed == 0:
        print(f"All validation checks passed! ✨ ({passed}/{passed + failed})")
        return 0
    else:
        print(f"Validation failed: {failed}/{passed + failed} checks failed")
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobradar", description="JobRadar-AI internship radar")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Fetch and process internship sources")
    scan.add_argument("--once", action="store_true", help="Single scan pass")
    scan.add_argument("--loop", action="store_true", help="Scan forever")
    scan.add_argument("--interval", type=int, default=300, help="Loop interval seconds")
    scan.add_argument(
        "--alert-all",
        action="store_true",
        help="Notify on first scan too (default: seed DB, alert later)",
    )
    scan.set_defaults(func=cmd_scan)

    health = sub.add_parser("health", help="Health check")
    health.set_defaults(func=cmd_health)

    ping = sub.add_parser("ping-grok", help="Ping configured Grok Bot webhooks")
    ping.set_defaults(func=cmd_ping_grok)

    td = sub.add_parser("test-discord", help="Post a test message to Discord")
    td.set_defaults(func=cmd_test_discord)

    tn_push = sub.add_parser("test-ntfy", help="Send a test phone push via ntfy (free)")
    tn_push.set_defaults(func=cmd_test_ntfy)

    tt = sub.add_parser("test-telegram", help="Send a test Telegram message (free)")
    tt.set_defaults(func=cmd_test_telegram)

    tn = sub.add_parser("test-notion", help="Check Notion database access")
    tn.set_defaults(func=cmd_test_notion)

    nb = sub.add_parser("notion-backfill", help="Push existing jobs to Notion")
    nb.add_argument("--priority-only", action="store_true", default=True)
    nb.add_argument("--all", dest="priority_only", action="store_false")
    nb.add_argument("--limit", type=int, default=None)
    nb.add_argument(
        "--status",
        default="Backlog",
        help="Notion Status for backfilled rows (default Backlog; no Discord)",
    )
    nb.set_defaults(func=cmd_notion_backfill)

    ga = sub.add_parser("gmail-auth", help="Browser OAuth for Gmail")
    ga.set_defaults(func=cmd_gmail_auth)

    gs = sub.add_parser("gmail-sync", help="Classify recent mail and update tracker")
    gs.add_argument("--days", type=int, default=7)
    gs.add_argument("--max", type=int, default=100)
    gs.set_defaults(func=cmd_gmail_sync)

    gr = sub.add_parser(
        "gmail-reorganize",
        help="Backfill job threads with exclusive JobRadar/* labels (see docs/GMAIL_ORGANIZATION.md)",
    )
    gr.add_argument("--days", type=int, default=365, help="Lookback window")
    gr.add_argument("--max-threads", type=int, default=500, help="Max threads to process")
    gr.add_argument("--dry-run", action="store_true", help="Count only; do not modify Gmail")
    gr.set_defaults(func=cmd_gmail_reorganize)

    wr = sub.add_parser("weekly-report", help="Write docs/weekly/YYYY-MM-DD.md stats")
    wr.set_defaults(func=cmd_weekly_report)

    vl = sub.add_parser("verify-links", help="Probe job URLs for liveness")
    vl.add_argument("--priority-only", action="store_true", default=False, help="Check only priority jobs")
    vl.add_argument("--limit", type=int, default=None, help="Limit number of jobs to check")
    vl.add_argument("--urls", nargs="+", help="Check specific URLs instead of SQLite jobs")
    vl.add_argument("--mark-bad", action="store_true", help="Mark bad URLs as closed (silent)")
    vl.add_argument("--verbose", action="store_true", help="Print each URL result")
    vl.set_defaults(func=cmd_verify_links)

    db_init = sub.add_parser("db-init", help="Initialize empty DB schema (see scripts/fresh_db_backup.sh)")
    db_init.set_defaults(func=cmd_db_init)
    
    db_refresh = sub.add_parser(
        "db-refresh",
        help="Safe DB refresh: backup existing DB, then recreate empty schema",
    )
    db_refresh.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup (testing only; requires interactive confirmation)",
    )
    db_refresh.set_defaults(func=cmd_db_refresh)
    
    refresh = sub.add_parser("refresh-jobs", help="Silent job field refresh (no notifications)")
    refresh.set_defaults(func=cmd_refresh_jobs)
    qb = sub.add_parser(
        "quarantine-bad-urls",
        help="Scan existing jobs and mark bad/empty URLs as closed (silent, no alerts)",
    )
    qb.set_defaults(func=cmd_quarantine_bad_urls)

    vs = sub.add_parser(
        "validate-scan",
        help="Comprehensive scan validation harness (non-destructive, no live notifications)",
    )
    vs.set_defaults(func=cmd_validate_scan)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan" and not (args.once or args.loop):
        parser.error("scan requires --once or --loop")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
