"""Smoke tests for the kalakal package scaffold."""

from importlib import metadata

import kalakal


def test_package_imports() -> None:
    assert kalakal.__name__ == "kalakal"


def test_version_metadata_matches_distribution() -> None:
    assert isinstance(kalakal.__version__, str)
    assert kalakal.__version__ == metadata.version("kalakal-agent")
