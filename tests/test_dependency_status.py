from __future__ import annotations

from app.services import dependency_status
from app.services.dependency_status import get_optional_dependency_status


def test_dependency_status_returns_dict():
    status = get_optional_dependency_status()

    assert isinstance(status, dict)


def test_dependency_status_contains_required_fields():
    status = get_optional_dependency_status()

    assert {"dowhy", "econml", "langgraph", "reportlab", "deepseek_configured"}.issubset(status)


def test_dependency_status_uses_stable_bool_fields():
    status = get_optional_dependency_status()

    for key in ["dowhy", "econml", "langgraph", "reportlab"]:
        assert isinstance(status[key]["available"], bool)
        assert status[key]["status"] in {"available", "unavailable"}
    assert isinstance(status["deepseek_configured"]["configured"], bool)
    assert status["deepseek_configured"]["status"] in {"configured", "not_configured"}


def test_missing_optional_dependencies_do_not_raise(monkeypatch):
    original_find_spec = dependency_status.importlib.util.find_spec

    def fake_find_spec(name: str):
        if name in {"dowhy", "econml", "langgraph", "reportlab"}:
            return None
        return original_find_spec(name)

    monkeypatch.setattr(dependency_status.importlib.util, "find_spec", fake_find_spec)

    status = get_optional_dependency_status()

    assert status["dowhy"]["available"] is False
    assert status["econml"]["available"] is False
    assert status["langgraph"]["available"] is False
    assert status["reportlab"]["available"] is False


def test_deepseek_status_does_not_expose_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "super-secret-test-key")

    status = get_optional_dependency_status()

    assert status["deepseek_configured"]["configured"] is True
    assert "super-secret-test-key" not in str(status)
