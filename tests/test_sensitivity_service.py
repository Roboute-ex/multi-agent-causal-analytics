from __future__ import annotations

from app.core.schemas import AnalysisRequest, EstimationResult, PipelineBundle
from app.services.sensitivity_service import build_sensitivity_summary, summarize_refutation_stability


def _estimate(ate: float = 0.2, refutations: dict | None = None) -> EstimationResult:
    return EstimationResult(
        status="ok",
        method="test",
        estimand_text="test",
        ate=ate,
        refutations=refutations
        if refutations is not None
        else {
            "placebo_treatment": {"status": "ok", "new_effect": 0.01},
            "random_common_cause": {"status": "ok", "new_effect": 0.19},
            "data_subset": {"status": "ok", "new_effect": 0.21},
        },
    )


def _bundle(estimate: EstimationResult | None) -> PipelineBundle:
    return PipelineBundle(
        request=AnalysisRequest(
            dataset_path="in_memory.csv",
            treatment="coupon",
            outcome="purchase",
        ),
        estimate=estimate,
    )


def test_sensitivity_summary_stable_refutations():
    summary = summarize_refutation_stability(_estimate())

    assert summary["status"] == "ok"
    assert summary["sensitivity_status"] == "stable"
    assert summary["refutation_details"]["random_common_cause"]["stable_direction"] is True


def test_sensitivity_summary_detects_unstable_direction():
    estimate = _estimate(
        refutations={
            "placebo_treatment": {"status": "ok", "new_effect": -0.2},
            "random_common_cause": {"status": "ok", "new_effect": -0.1},
            "data_subset": {"status": "ok", "new_effect": 0.18},
        }
    )

    summary = summarize_refutation_stability(estimate)

    assert summary["sensitivity_status"] == "unstable"
    assert any("changed or weakened" in warning for warning in summary["warnings"])


def test_sensitivity_summary_handles_missing_refutations():
    summary = summarize_refutation_stability(_estimate(refutations={}))

    assert summary["sensitivity_status"] == "skipped"
    assert any("Missing refutation results" in warning for warning in summary["warnings"])


def test_sensitivity_summary_handles_error_refutation():
    estimate = _estimate(
        refutations={
            "placebo_treatment": {"status": "error", "error": "failed"},
            "random_common_cause": {"status": "ok", "new_effect": 0.2},
            "data_subset": {"status": "ok", "new_effect": 0.2},
        }
    )

    summary = summarize_refutation_stability(estimate)

    assert summary["sensitivity_status"] == "partially_stable"
    assert any("failed" in warning for warning in summary["warnings"])


def test_build_sensitivity_summary_skips_without_estimate():
    summary = build_sensitivity_summary(_bundle(None))

    assert summary["status"] == "skipped"
    assert summary["sensitivity_status"] == "skipped"


def test_build_sensitivity_summary_skips_failed_estimate():
    estimate = EstimationResult(
        status="error",
        method="test",
        estimand_text="",
        error="no overlap",
    )

    summary = build_sensitivity_summary(_bundle(estimate))

    assert summary["status"] == "skipped"
    assert "no overlap" in summary["warnings"][0]
