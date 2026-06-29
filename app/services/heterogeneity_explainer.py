from __future__ import annotations

import importlib.util
from typing import Any

from app.core.schemas import CateResult


def explain_heterogeneity(
    cate: CateResult | None,
    effect_modifiers: list[str] | None = None,
    estimator: Any | None = None,
) -> dict[str, Any]:
    """Create a business-readable CATE heterogeneity explanation with graceful fallback."""
    modifiers = list(effect_modifiers or [])
    if cate is None:
        return _skipped("CATE result is unavailable.", modifiers)
    if cate.status != "ok":
        return _skipped(cate.error or f"CATE status is {cate.status}.", modifiers, status=cate.status)

    segment_summary = cate.segment_summary or {}
    top_effect_modifiers = modifiers[:3]
    business_interpretation = _business_interpretation(cate, top_effect_modifiers, segment_summary)
    shap_summary = _optional_shap_summary(estimator)

    limitations = [
        "CATE patterns are exploratory and should be validated before targeting decisions.",
        "Effect modifier interpretation depends on the user-selected variables and available data.",
        "Heterogeneity estimates may be unstable with small samples or weak overlap.",
    ]
    if shap_summary["status"] != "ok":
        limitations.append(shap_summary["message"])

    return {
        "status": "ok",
        "cate_status": cate.status,
        "top_effect_modifiers": top_effect_modifiers,
        "segment_effect_summary": segment_summary,
        "business_interpretation": business_interpretation,
        "shap_summary": shap_summary,
        "limitations": limitations,
    }


def _skipped(reason: str, modifiers: list[str], status: str = "skipped") -> dict[str, Any]:
    return {
        "status": "skipped",
        "cate_status": status,
        "top_effect_modifiers": modifiers[:3],
        "segment_effect_summary": {},
        "business_interpretation": "CATE heterogeneity explanation is unavailable.",
        "shap_summary": {
            "status": "skipped",
            "message": "SHAP explanation was not attempted because CATE is unavailable.",
        },
        "limitations": [
            reason,
            "Heterogeneity interpretation requires a successful CATE estimate.",
        ],
    }


def _business_interpretation(
    cate: CateResult,
    modifiers: list[str],
    segment_summary: dict[str, Any],
) -> str:
    if not segment_summary:
        return (
            "CATE was estimated, but no segment summary is available. Treat the average "
            "heterogeneity signal as exploratory."
        )

    high = _safe_float(segment_summary.get("high_group_mean"))
    low = _safe_float(segment_summary.get("low_group_mean"))
    modifier_text = ", ".join(modifiers) if modifiers else "the selected effect modifiers"
    if high is not None and low is not None:
        if high > low:
            return (
                f"Estimated treatment effects appear stronger in the higher {modifier_text} segment. "
                "Use this as a hypothesis for targeting, not as final targeting policy."
            )
        if high < low:
            return (
                f"Estimated treatment effects appear stronger in the lower {modifier_text} segment. "
                "Validate this pattern before operational use."
            )
        return (
            f"Estimated treatment effects look similar across {modifier_text} segments. "
            "The practical heterogeneity signal may be limited."
        )
    return (
        "CATE segment details are available but not in a standard high/low format. "
        "Review the segment summary before drawing targeting conclusions."
    )


def _optional_shap_summary(estimator: Any | None) -> dict[str, str]:
    if estimator is None:
        return {"status": "skipped", "message": "No CATE estimator object was provided for SHAP."}
    if importlib.util.find_spec("shap") is None:
        return {"status": "skipped", "message": "SHAP is not installed; using segment summary fallback."}
    if not hasattr(estimator, "shap_values"):
        return {
            "status": "skipped",
            "message": "The CATE estimator does not expose shap_values; using segment summary fallback.",
        }
    return {
        "status": "available",
        "message": "Estimator exposes shap_values, but v0.8 only reports a safe summary fallback.",
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
