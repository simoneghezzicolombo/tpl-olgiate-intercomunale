"""Pytest configuration: custom marks registration."""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: test that performs real network requests (Overpass, Socrata, ISTAT, etc.). "
        "Skip with: pytest -m 'not network'",
    )
