from __future__ import annotations

from app.core.schemas import CateResult
from app.services.heterogeneity_explainer import explain_heterogeneity


def test_heterogeneity_explainer_ok_with_segment_summary():
    cate = CateResult(
        status="ok",
        cate_mean=0.12,
        cate_std=0.03,
        segment_summary={"high_group_mean": 0.18, "low_group_mean": 0.05},
    )

    summary = explain_heterogeneity(cate, effect_modifiers=["visits", "income"])

    assert summary["status"] == "ok"
    assert summary["cate_status"] == "ok"
    assert summary["top_effect_modifiers"] == ["visits", "income"]
    assert "higher visits, income segment" in summary["business_interpretation"]


def test_heterogeneity_explainer_skips_when_cate_skipped():
    cate = CateResult(status="skipped", error="EconML not installed")

    summary = explain_heterogeneity(cate, effect_modifiers=["visits"])

    assert summary["status"] == "skipped"
    assert summary["cate_status"] == "skipped"
    assert "EconML not installed" in summary["limitations"][0]


def test_heterogeneity_explainer_skips_when_cate_error():
    cate = CateResult(status="error", error="CATE failed")

    summary = explain_heterogeneity(cate, effect_modifiers=["visits"])

    assert summary["status"] == "skipped"
    assert summary["cate_status"] == "error"
    assert "CATE failed" in summary["limitations"][0]


def test_heterogeneity_explainer_handles_missing_cate():
    summary = explain_heterogeneity(None, effect_modifiers=["visits"])

    assert summary["status"] == "skipped"
    assert summary["top_effect_modifiers"] == ["visits"]


def test_heterogeneity_explainer_graceful_shap_fallback_without_estimator():
    cate = CateResult(
        status="ok",
        segment_summary={"high_group_mean": 0.05, "low_group_mean": 0.10},
    )

    summary = explain_heterogeneity(cate, effect_modifiers=["visits"], estimator=None)

    assert summary["shap_summary"]["status"] == "skipped"
    assert "lower visits segment" in summary["business_interpretation"]


def test_heterogeneity_explainer_handles_nonstandard_segment_summary():
    cate = CateResult(status="ok", segment_summary={"segment_a": 0.1})

    summary = explain_heterogeneity(cate, effect_modifiers=[])

    assert summary["status"] == "ok"
    assert "not in a standard high/low format" in summary["business_interpretation"]
