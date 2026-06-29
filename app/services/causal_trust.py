from __future__ import annotations

from typing import Any

from app.core.schemas import PipelineBundle


def build_causal_trust_summary(
    bundle: PipelineBundle | None,
    data_quality: dict[str, Any] | None = None,
    sensitivity_summary: dict[str, Any] | None = None,
    heterogeneity_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate causal outputs into conservative trust guidance for business users."""
    key_warnings: list[str] = []
    recommendations: list[str] = [
        "Treat this as an observational causal analysis, not as randomized-experiment proof.",
        "Review whether important confounders are missing before making business decisions.",
    ]

    if bundle is None or bundle.estimate is None:
        return {
            "status": "error",
            "effect_direction": "unknown",
            "robustness_level": "unknown",
            "key_warnings": ["ATE estimate is unavailable."],
            "recommendations": recommendations,
        }

    estimate = bundle.estimate
    effect_direction = _effect_direction(estimate.ate)
    if estimate.status == "error":
        key_warnings.append(estimate.error or "ATE estimation failed.")
    if estimate.warnings:
        key_warnings.extend(str(item) for item in estimate.warnings)
    if bundle.review and bundle.review.warnings:
        key_warnings.extend(str(item) for item in bundle.review.warnings)

    dq_status = (data_quality or {}).get("status")
    dq_warnings = list((data_quality or {}).get("warnings", []))
    if dq_status in {"warning", "error"}:
        key_warnings.append("Sample quality risk is present in the data quality checks.")
    key_warnings.extend(str(item) for item in dq_warnings[:5])

    sensitivity_status = (sensitivity_summary or {}).get("sensitivity_status", "unknown")
    sensitivity_warnings = list((sensitivity_summary or {}).get("warnings", []))
    key_warnings.extend(str(item) for item in sensitivity_warnings[:5])

    heterogeneity_status = (heterogeneity_summary or {}).get("cate_status", "unknown")
    if heterogeneity_status in {"skipped", "error"}:
        key_warnings.append("CATE heterogeneity evidence is unavailable or incomplete.")

    robustness_level = _robustness_level(
        estimate_status=estimate.status,
        sensitivity_status=sensitivity_status,
        review_status=bundle.review.status if bundle.review else "unknown",
        data_quality_status=dq_status or "unknown",
        warning_count=len(key_warnings),
    )

    if robustness_level == "high":
        recommendations.append(
            "Results look directionally stable across available checks, but still require domain review."
        )
    elif robustness_level == "medium":
        recommendations.append(
            "Use the result as directional evidence and validate with additional robustness checks or experiments."
        )
    else:
        recommendations.append(
            "Do not use this result alone for high-stakes decisions; collect better data or run an experiment."
        )

    if effect_direction == "near_zero":
        recommendations.append("The estimated effect is close to zero; practical significance may be limited.")
    elif effect_direction == "unknown":
        recommendations.append("No interpretable ATE direction is available.")

    status = "ok" if robustness_level in {"high", "medium"} else "warning"
    if estimate.status == "error":
        status = "error"

    return {
        "status": status,
        "effect_direction": effect_direction,
        "robustness_level": robustness_level,
        "key_warnings": _dedupe(key_warnings),
        "recommendations": _dedupe(recommendations),
    }


def _effect_direction(ate: Any) -> str:
    value = _safe_float(ate)
    if value is None:
        return "unknown"
    if abs(value) < 0.01:
        return "near_zero"
    return "positive" if value > 0 else "negative"


def _robustness_level(
    estimate_status: str,
    sensitivity_status: str,
    review_status: str,
    data_quality_status: str,
    warning_count: int,
) -> str:
    if estimate_status == "error":
        return "unknown"
    if sensitivity_status == "stable" and review_status == "ok" and data_quality_status in {"ok", "unknown"}:
        return "high" if warning_count == 0 else "medium"
    if sensitivity_status in {"stable", "partially_stable"} and warning_count <= 4:
        return "medium"
    if sensitivity_status in {"unstable", "skipped"} or data_quality_status == "error":
        return "low"
    return "unknown"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
