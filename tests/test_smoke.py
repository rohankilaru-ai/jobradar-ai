import os

from jobradar import __version__
from jobradar.cli import build_parser, main


def test_version():
    assert __version__ == "0.1.0"


def test_health_cli(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "health.db"))
    assert main(["health"]) == 0
    out = capsys.readouterr().out
    assert "jobradar 0.1.0 ok" in out


def test_ping_grok(capsys):
    assert main(["ping-grok"]) == 0
    assert "skip" in capsys.readouterr().out.lower()


def test_test_discord_skips(capsys, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert main(["test-discord"]) == 0
    assert "skipped" in capsys.readouterr().out.lower()


def test_parser_has_product_commands():
    p = build_parser()
    names = {a.dest for a in p._get_positional_actions() if hasattr(a, "choices") or True}
    help_txt = p.format_help()
    for cmd in (
        "test-discord",
        "test-ntfy",
        "test-telegram",
        "test-notion",
        "gmail-auth",
        "gmail-sync",
        "notion-backfill",
    ):
        assert cmd in help_txt
