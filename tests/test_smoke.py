from jobradar import __version__
from jobradar.cli import build_parser, main


def test_version():
    assert __version__ == "0.1.0"


def test_health_cli(capsys):
    assert main(["health"]) == 0
    out = capsys.readouterr().out
    assert "jobradar 0.1.0 ok" in out


def test_scan_once(capsys):
    assert main(["scan", "--once"]) == 0
    assert "stub" in capsys.readouterr().out


def test_parser_has_commands():
    p = build_parser()
    assert p.prog == "jobradar"
