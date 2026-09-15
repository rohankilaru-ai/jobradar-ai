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
    from jobradar import gmail as gmail_mod
    from jobradar import notion as notion_mod

    print("notion: configured" if notion_mod.configured() else "notion: skipped until keys set")
    print("gmail: configured" if gmail_mod.configured() else "gmail: skipped until secrets/gmail-client.json")
    grok_on = any(
        os.environ.get(k)
        for k in ("GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_WEBHOOK_RESUME_MAPPER")
    )
    print("grok webhooks: configured" if grok_on else "grok webhooks: skipped until keys set")
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
            f"new={stats.new} notified={stats.notified}"
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
    if stats.source_errors:
        for err in stats.source_errors:
            print(f"source_error: {err}")
    return 0


def cmd_db_init(_: argparse.Namespace) -> int:
    """Initialize empty DB schema. Use scripts/fresh_db_backup.sh for safe resets."""
    db = Database()
    print(f"db initialized: {db.path}")
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
    refresh = sub.add_parser("refresh-jobs", help="Silent job field refresh (no notifications)")
    refresh.set_defaults(func=cmd_refresh_jobs)
    qb = sub.add_parser(
        "quarantine-bad-urls",
        help="Scan existing jobs and mark bad/empty URLs as closed (silent, no alerts)",
    )
    qb.set_defaults(func=cmd_quarantine_bad_urls)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan" and not (args.once or args.loop):
        parser.error("scan requires --once or --loop")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
