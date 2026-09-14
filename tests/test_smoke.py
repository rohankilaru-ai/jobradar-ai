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


def test_parser_has_commands():
    p = build_parser()
    assert p.prog == "jobradar"
