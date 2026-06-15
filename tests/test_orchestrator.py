from __future__ import annotations

import importlib.util
from numbers import Real

from app.core.orchestrator import AnalyticsTeamOrchestrator
from app.core.schemas import AnalysisRequest
from data.generate_synthetic import make_synthetic_marketing_data

REQUIRED_REFUTATIONS = {"placebo_treatment", "random_common_cause", "data_subset"}


def test_pipeline_runs_end_to_end():
    df = make_synthetic_marketing_data(n=800, seed=123)
    request = AnalysisRequest(
        question="优惠券是否提升购买概率？",
        dataset_path="in_memory.csv",
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )

    bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)

    assert bundle.profile is not None
    assert bundle.profile.n_rows == 800
    assert bundle.method is not None
    assert bundle.method.primary == "DoWhy backdoor.linear_regression（可用时优先）"
    assert bundle.estimate is not None
    assert bundle.estimate.status == "ok"
    assert isinstance(bundle.estimate.ate, Real)
    assert bundle.estimate.refutations
    assert REQUIRED_REFUTATIONS.issubset(bundle.estimate.refutations)
    if importlib.util.find_spec("dowhy"):
        assert bundle.estimate.method == "DoWhy backdoor.linear_regression"
        assert isinstance(bundle.estimate.refutations["placebo_treatment"], dict)
        assert "new_effect" in bundle.estimate.refutations["placebo_treatment"]
    assert bundle.cate is not None
    if importlib.util.find_spec("econml"):
        assert bundle.cate.status == "ok"
        assert isinstance(bundle.cate.cate_mean, float)
        assert isinstance(bundle.cate.cate_std, float)
        assert bundle.cate.segment_summary["high_group_mean"] > bundle.cate.segment_summary["low_group_mean"]
    else:
        assert bundle.cate.status == "skipped"
    assert bundle.cate.status in {"ok", "skipped", "error"}
    assert bundle.review is not None
    assert bundle.review.status in {"ok", "warning"}
    assert bundle.review.checks["has_ate_estimate"] is True
    assert bundle.review.checks["has_refutations"] is True
    assert bundle.review.checks["has_required_refutations"] is True
    assert bundle.review.checks["cate_optional_handled"] is True
    assert "placebo_near_zero" in bundle.review.checks
    assert bundle.report_markdown is not None
    assert "Multi-Agent Causal Analytics Team Report" in bundle.report_markdown
    assert [result.agent for result in bundle.agent_logs] == [
        "coordinator",
        "data_engineer",
        "statistician",
        "causal",
        "heterogeneity",
        "reviewer",
        "reporter",
        "deepseek_reporter",
    ]
    assert bundle.agent_logs[-1].status == "skipped"
