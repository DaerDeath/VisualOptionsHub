"""Fixtures globales: la grabadora nunca escribe en ~/.visual-options en tests."""

import pytest

from visual_options.stream import persistence


@pytest.fixture(autouse=True)
def isolated_recorder_db(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DEFAULT_DB", tmp_path / "sessions-test.db")
