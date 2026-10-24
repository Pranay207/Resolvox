"""Unit tests stay offline; live generation is always explicitly requested."""
import pytest

@pytest.fixture(autouse=True)
def offline_default(monkeypatch):
    monkeypatch.setenv('COMPOSE_WITH_LLM','false')
