from __future__ import annotations

import pytest

from app.core.schemas import AnalysisRequest, EstimationResult, PipelineBundle, ReviewResult
from app.services.causal_trust import build_causal_trust_summary


def _bundle(ate: float | None, estimate_status: str = "ok", review_status: str = "ok") -> PipelineBundle:
    return PipelineBundle(
        request=AnalysisRequest(
            dataset_path="in_memory.csv",
            treatment="coupon",
            outcome="purchase",
        ),
        estimate=EstimationResult(
            status=estimate_status,
            method="test",
            estimand_text="test",
            ate=ate,
            error="failed estimate" if estimate_status == "error" else None,
        ),
        review=ReviewResult(status=review_status, checks={}, warnings=[]),
    )


@pytest.mark.parametrize(
    ("ate", "direction"),
    [(0.2, "positive"), (-0.2, "negative"), (0.001, "near_zero"), (None, "unknown")],
)
def test_causal_trust_effect_direction(ate, direction):
    summary = build_causal_trust_summary(
        _bundle(ate),
        data_quality={"status": "ok", "warnings": []},
        sensitivity_summary={"sensitivity_status": "stable", "warnings": []},
        heterogeneity_summary={"cate_status": "ok"},
    )

    assert summary["effect_direction"] == direction


def test_causal_trust_high_robustness_without_warnings():
    summary = build_causal_trust_summary(
        _bundle(0.2),
        data_quality={"status": "ok", "warnings": []},
        sensitivity_summary={"sensitivity_status": "stable", "warnings": []},
        heterogeneity_summary={"cate_status": "ok"},
    )

    assert summary["status"] == "ok"
    assert summary["robustness_level"] == "high"


def test_causal_trust_medium_with_partial_stability():
    summary = build_causal_trust_summary(
        _bundle(0.2, review_status="warning"),
        data_quality={"status": "warning", "warnings": ["missingness risk"]},
        sensitivity_summary={"sensitivity_status": "partially_stable", "warnings": []},
        heterogeneity_summary={"cate_status": "ok"},
    )

    assert summary["robustness_level"] == "medium"
    assert any("Sample quality risk" in warning for warning in summary["key_warnings"])


def test_causal_trust_low_when_sensitivity_unstable():
    summary = build_causal_trust_summary(
        _bundle(0.2),
        data_quality={"status": "ok", "warnings": []},
        sensitivity_summary={"sensitivity_status": "unstable", "warnings": ["direction changed"]},
        heterogeneity_summary={"cate_status": "skipped"},
    )

    assert summary["status"] == "warning"
    assert summary["robustness_level"] == "low"
    assert any("direction changed" in warning for warning in summary["key_warnings"])


def test_causal_trust_error_without_estimate():
    summary = build_causal_trust_summary(None)

    assert summary["status"] == "error"
    assert summary["effect_direction"] == "unknown"


def test_causal_trust_mentions_observational_limitations():
    summary = build_causal_trust_summary(
        _bundle(0.2),
        data_quality={"status": "ok", "warnings": []},
        sensitivity_summary={"sensitivity_status": "stable", "warnings": []},
        heterogeneity_summary={"cate_status": "ok"},
    )

    assert any("observational causal analysis" in item for item in summary["recommendations"])
    assert any("confounders" in item for item in summary["recommendations"])
