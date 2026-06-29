from __future__ import annotations

from typing import Any

from app.core.schemas import EstimationResult, PipelineBundle


REQUIRED_REFUTATIONS = ("placebo_treatment", "random_common_cause", "data_subset")


def build_sensitivity_summary(bundle: PipelineBundle | None) -> dict[str, Any]:
    """Summarize robustness from existing refutation payloads without extra dependencies."""
    if bundle is None or bundle.estimate is None:
        return _skipped("No estimation result is available for sensitivity summary.")

    estimate = bundle.estimate
    if estimate.status == "error":
        return _skipped(estimate.error or "ATE estimation failed, so sensitivity summary is unavailable.")

    if estimate.ate is None:
        return _skipped("ATE is unavailable, so sensitivity summary is unavailable.")

    return summarize_refutation_stability(estimate)


def summarize_refutation_stability(estimate: EstimationResult) -> dict[str, Any]:
    baseline = _safe_float(estimate.ate)
    if baseline is None:
        return _skipped("ATE is unavailable, so sensitivity summary is unavailable.")

    refutations = estimate.refutations or {}
    missing = [name for name in REQUIRED_REFUTATIONS if name not in refutations]
    notes: list[str] = []
    warnings: list[str] = []
    stable_checks: list[bool] = []
    details: dict[str, Any] = {}

    for name in REQUIRED_REFUTATIONS:
        payload = refutations.get(name)
        if payload is None:
            details[name] = {"status": "missing", "stable_direction": None}
            continue
        if not isinstance(payload, dict):
            details[name] = {"status": "unknown", "stable_direction": None}
            warnings.append(f"{name} returned a non-standard payload.")
            continue
        if payload.get("status") == "error":
            details[name] = {
                "status": "error",
                "stable_direction": None,
                "error": payload.get("error"),
            }
            warnings.append(f"{name} failed: {payload.get('error', 'unknown error')}")
            continue

        new_effect = _safe_float(payload.get("new_effect"))
        if new_effect is None:
            details[name] = {"status": payload.get("status", "unknown"), "stable_direction": None}
            warnings.append(f"{name} did not provide a numeric new_effect.")
            continue

        stable_direction = _same_direction_or_near_zero(baseline, new_effect)
        stable_checks.append(stable_direction)
        details[name] = {
            "status": payload.get("status", "ok"),
            "estimated_effect": _safe_float(payload.get("estimated_effect")),
            "new_effect": new_effect,
            "absolute_difference_from_baseline": _safe_float(
                payload.get("absolute_difference_from_baseline")
            ),
            "stable_direction": stable_direction,
        }
        if stable_direction:
            notes.append(f"{name} kept the effect direction broadly stable.")
        else:
            warnings.append(f"{name} changed or weakened the effect direction.")

    if missing:
        warnings.append(f"Missing refutation results: {', '.join(missing)}.")

    if not stable_checks:
        sensitivity_status = "skipped"
    elif all(stable_checks) and not missing and not warnings:
        sensitivity_status = "stable"
    elif sum(stable_checks) >= max(1, len(stable_checks) - 1):
        sensitivity_status = "partially_stable"
    else:
        sensitivity_status = "unstable"

    limitations = [
        "This is a conservative summary of existing refutation checks, not a full formal sensitivity analysis.",
        "Observational causal claims may still be affected by unmeasured confounding.",
        "Stable refutations increase confidence but do not prove causal identification.",
    ]

    return {
        "status": "ok" if sensitivity_status != "skipped" else "skipped",
        "sensitivity_status": sensitivity_status,
        "stability_notes": notes,
        "warnings": warnings,
        "refutation_details": details,
        "limitations": limitations,
    }


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "sensitivity_status": "skipped",
        "stability_notes": [],
        "warnings": [reason],
        "refutation_details": {},
        "limitations": [
            "Sensitivity summary requires a completed ATE estimate and refutation results.",
            "Skipped sensitivity output should not be interpreted as evidence of robustness.",
        ],
    }


def _same_direction_or_near_zero(baseline: float, value: float) -> bool:
    tolerance = max(0.01, abs(baseline) * 0.10)
    if abs(baseline) <= tolerance:
        return abs(value) <= tolerance
    return (baseline > 0 and value > -tolerance) or (baseline < 0 and value < tolerance)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
