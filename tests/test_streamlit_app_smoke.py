from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app" / "ui_streamlit.py"


def test_streamlit_initial_page_renders_without_uncaught_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DEMO_MODE", raising=False)

    app = _run_app()

    _assert_no_uncaught_exceptions(app)
    page_text = _all_text(app)
    for expected in [
        "Multi-Agent Causal Analytics",
        "Data Quality Summary",
        "Deployment / Optional Dependency Status",
        "LangGraph",
        "LLM-assisted Variable Recommendation",
        "public demo",
    ]:
        assert expected in page_text


def test_streamlit_demo_mode_shows_public_safety_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEMO_MODE", "true")

    app = _run_app()

    _assert_no_uncaught_exceptions(app)
    page_text = _all_text(app)
    assert "Demo mode: `public demo`" in page_text
    assert "Do not upload private or sensitive data" in page_text
    assert "built-in sample dataset" in page_text
    assert "Optional Dependency Status" in page_text


def test_streamlit_optional_dependency_status_panel_handles_unavailable_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.dependency_status as dependency_status

    monkeypatch.setattr(
        dependency_status,
        "get_optional_dependency_status",
        lambda: {
            "dowhy": {"label": "DoWhy", "available": False, "status": "unavailable"},
            "econml": {"label": "EconML", "available": False, "status": "unavailable"},
            "langgraph": {"label": "LangGraph", "available": False, "status": "unavailable"},
            "reportlab": {
                "label": "ReportLab PDF export",
                "available": False,
                "status": "unavailable",
            },
            "deepseek_configured": {
                "label": "DeepSeek API",
                "configured": False,
                "status": "not_configured",
            },
        },
    )

    app = _run_app()

    _assert_no_uncaught_exceptions(app)
    page_text = _all_text(app)
    assert "Deployment / Optional Dependency Status" in page_text
    assert "Optional dependencies can be installed only when needed." in page_text
    assert "API key values are never displayed." in page_text


def test_streamlit_default_analysis_result_sections_and_downloads_render() -> None:
    app = _run_app()
    _button_by_label(app, "运行 Multi-Agent 因果分析").click().run()

    _assert_no_uncaught_exceptions(app)
    page_text = _all_text(app)
    for expected in [
        "Causal Trust Summary",
        "Robustness / Sensitivity Notes",
        "Heterogeneity Explanation",
        "Data Quality Summary",
        "LangGraph",
        "Multi-Agent Causal Analytics Team Report",
    ]:
        assert expected in page_text

    download_labels = [button.label for button in app.get("download_button")]
    assert "下载 Markdown 报告" in download_labels
    assert "下载 HTML 报告" in download_labels


def _run_app() -> Any:
    return AppTest.from_file(str(APP_PATH), default_timeout=60).run()


def _assert_no_uncaught_exceptions(app: Any) -> None:
    assert not app.exception, [str(exception) for exception in app.exception]


def _button_by_label(app: Any, label: str) -> Any:
    for button in app.button:
        if button.label == label:
            return button
    available = [button.label for button in app.button]
    raise AssertionError(f"Could not find button {label!r}; available buttons: {available!r}")


def _all_text(app: Any) -> str:
    parts: list[str] = []
    for element_type in [
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "info",
        "warning",
        "success",
        "error",
        "radio",
        "text_input",
        "selectbox",
        "multiselect",
        "checkbox",
        "button",
        "download_button",
        "expander",
        "tabs",
    ]:
        try:
            elements = app.get(element_type)
        except Exception:
            elements = getattr(app, element_type, [])
        for element in elements:
            for attribute in ("value", "label"):
                value = getattr(element, attribute, None)
                if value:
                    parts.append(str(value))
    return "\n".join(parts)
