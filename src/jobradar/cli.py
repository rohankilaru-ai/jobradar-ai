"""JobRadar CLI entrypoints (stubs until pipeline lands)."""

from __future__ import annotations

import argparse
import sys
import time

from jobradar import __version__


def cmd_health(_: argparse.Namespace) -> int:
    print(f"jobradar {__version__} ok")
    print("db: not configured yet")
    print("notifiers: mock")
    print("grok webhooks: skipped until keys set")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    if args.loop:
        interval = args.interval
        print(f"scan loop stub — interval={interval}s (pipeline not implemented yet)")
        try:
            while True:
                print("scan --once stub: no sources fetched yet")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("stopped")
            return 0
    print("scan --once stub: no sources fetched yet")
    return 0


def cmd_ping_grok(_: argparse.Namespace) -> int:
    print("ping-grok stub: empty webhook env → skip (OK)")
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
