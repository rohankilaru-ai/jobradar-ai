"""JobRadar CLI entrypoints."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from jobradar import __version__
from jobradar.db import Database
from jobradar.director import ping_configured
from jobradar.notify import (
    discord_configured,
    ntfy_configured,
    send_discord,
    send_ntfy,
    send_telegram,
    telegram_configured,
)
from jobradar.pipeline import run_scan

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
        print("skipped (no DISCORD_WEBHOOK_URL). See docs/ACCOUNTS.md")
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


def cmd_verify_links(args: argparse.Namespace) -> int:
    """Verify job URLs from DB (forces link probe ON for self-check)."""
    import os
    from jobradar.notify import job_notify_block_reason, sanitize_job_url
    
    # Force link probe ON for verify-links
    os.environ["JOBRADAR_LINK_PROBE"] = "1"
    
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, 
                       format="%(levelname)s %(name)s: %(message)s")
    db = Database()
    
    jobs = db.list_jobs(priority_only=args.priority_only, limit=args.limit)
    print(f"Checking {len(jobs)} jobs...")
    
    passed = 0
    failed_jobs = []
    
    for job in jobs:
        block_reason = job_notify_block_reason(job)
        
        if block_reason:
            failed_jobs.append((job, block_reason))
        else:
            passed += 1
            if args.verbose:
                print(f"✓ {job.company} | {job.title}")
                print(f"   {sanitize_job_url(job.url)}")
    
    # Report failures
    if failed_jobs:
        print(f"\n❌ {len(failed_jobs)} failed:\n")
        for job, reason in failed_jobs:
            print(f"{job.company} | {job.title}")
            print(f"   └─ {reason}")
            if job.url:
                print(f"   └─ {job.url}")
            print()
    
    print(f"Results: {passed} passed, {len(failed_jobs)} failed")
    return 0 if len(failed_jobs) == 0 else 1


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

    vl = sub.add_parser("verify-links", help="Verify job URLs (forces link probe ON)")
    vl.add_argument("--priority-only", action="store_true", default=False)
    vl.add_argument("--limit", type=int, default=None, help="Max jobs to check")
    vl.add_argument("--verbose", "-v", action="store_true", help="Show all jobs, not just failures")
    vl.set_defaults(func=cmd_verify_links)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan" and not (args.once or args.loop):
        parser.error("scan requires --once or --loop")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
