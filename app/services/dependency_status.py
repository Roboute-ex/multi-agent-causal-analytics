from __future__ import annotations

import importlib.util
import os
from typing import Any


OPTIONAL_DEPENDENCIES = {
    "dowhy": "DoWhy",
    "econml": "EconML",
    "langgraph": "LangGraph",
    "reportlab": "ReportLab PDF export",
}


def get_optional_dependency_status() -> dict[str, Any]:
    """Return deployment-safe status for optional features without importing them."""
    status: dict[str, Any] = {}
    for package_name, label in OPTIONAL_DEPENDENCIES.items():
        available = importlib.util.find_spec(package_name) is not None
        status[package_name] = {
            "label": label,
            "available": available,
            "status": "available" if available else "unavailable",
        }

    deepseek_configured = bool(os.getenv("DEEPSEEK_API_KEY", "").strip())
    status["deepseek_configured"] = {
        "label": "DeepSeek API",
        "configured": deepseek_configured,
        "status": "configured" if deepseek_configured else "not_configured",
    }
    return status
