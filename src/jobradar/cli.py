"""JobRadar CLI entrypoints."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from jobradar import __version__
from jobradar.db import Database
from jobradar.pipeline import run_scan


def cmd_health(_: argparse.Namespace) -> int:
    db = Database()
    print(f"jobradar {__version__} ok")
    print(f"db: {db.path} ({db.count_jobs()} jobs)")
    print("notifiers: mock")
    print("grok webhooks: skipped until keys set")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    def once() -> None:
        stats = run_scan()
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
    from jobradar.grok import configured_targets, ping_all

    targets = configured_targets()
    if not targets:
        print("ping-grok: no webhook keys set → skip (OK)")
        return 0
    print("ping-grok: targets=" + ",".join(targets))
    for name, status in ping_all().items():
        print(f"  {name}: {status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobradar", description="JobRadar-AI internship radar")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Fetch and process internship sources")
    scan.add_argument("--once", action="store_true", help="Single scan pass")
    scan.add_argument("--loop", action="store_true", help="Scan forever")
    scan.add_argument("--interval", type=int, default=300, help="Loop interval seconds")
    scan.set_defaults(func=cmd_scan)

    health = sub.add_parser("health", help="Health check")
    health.set_defaults(func=cmd_health)

    ping = sub.add_parser("ping-grok", help="Ping configured Grok Bot webhooks")
    ping.set_defaults(func=cmd_ping_grok)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan" and not (args.once or args.loop):
        parser.error("scan requires --once or --loop")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
