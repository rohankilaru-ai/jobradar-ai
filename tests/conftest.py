"""Pytest configuration and fixtures."""

import os
import pytest


@pytest.fixture(autouse=True)
def disable_link_probe_in_tests(monkeypatch):
    """Disable live HTTP probing in tests by default."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
