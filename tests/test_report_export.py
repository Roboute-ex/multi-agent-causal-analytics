from __future__ import annotations

from app.core.report import build_markdown_report
from app.core.report_export import build_html_report
from app.core.schemas import (
    AgentResult,
    AnalysisRequest,
    CateResult,
    DataProfile,
    EstimationResult,
    MethodRecommendation,
    PipelineBundle,
    ReviewResult,
)


def _sample_bundle(question: str = "优惠券是否提升购买率？") -> PipelineBundle:
    return PipelineBundle(
        request=AnalysisRequest(
            question=question,
            dataset_path="in_memory.csv",
            treatment="coupon",
            outcome="purchase",
            confounders=["age", "income"],
            effect_modifiers=["visits"],
        ),
        plan={"steps": ["数据画像", "ATE 因果效应估计"]},
        profile=DataProfile(
            n_rows=120,
            n_cols=5,
            numeric_columns=["coupon", "purchase", "age", "income", "visits"],
            categorical_columns=[],
            missing_rate={"coupon": 0.0, "purchase": 0.0},
            dtypes={"coupon": "int64", "purchase": "int64"},
        ),
        method=MethodRecommendation(
            primary="DoWhy backdoor.linear_regression",
            secondary="降级线性调整估计",
            assumptions=["用户选择了混杂变量。"],
            warnings=[],
        ),
        estimate=EstimationResult(
            status="ok",
            method="DoWhy backdoor.linear_regression",
            estimand_text="backdoor estimand",
            ate=0.123456,
            confidence_intervals=[0.01, 0.20],
            refutations={
                "placebo_treatment": {
                    "status": "ok",
                    "estimated_effect": 0.123456,
                    "new_effect": 0.001,
                    "absolute_difference_from_baseline": 0.122456,
                    "p_value": 0.41,
                },
                "random_common_cause": {
                    "status": "ok",
                    "estimated_effect": 0.123456,
                    "new_effect": 0.12,
                    "absolute_difference_from_baseline": 0.003456,
                },
            },
        ),
        cate=CateResult(
            status="skipped",
            method="EconML LinearDML",
            error="EconML 未安装，已跳过。",
        ),
        review=ReviewResult(
            status="warning",
            checks={"has_ate_estimate": True, "has_refutations": True},
            warnings=["请谨慎解释因果结果。"],
        ),
        report_markdown="# Multi-Agent Causal Analytics Team Report",
        agent_logs=[
            AgentResult(agent="data_engineer", status="ok"),
            AgentResult(agent="causal", status="ok"),
            AgentResult(agent="reviewer", status="warning"),
        ],
    )


def test_markdown_report_still_generates():
    markdown = build_markdown_report(_sample_bundle())

    assert markdown
    assert "Multi-Agent Causal Analytics Team Report" in markdown


def test_html_report_generates_core_sections():
    html = build_html_report(_sample_bundle())

    assert html
    assert "Multi-Agent Causal Analytics Team Report" in html
    assert "User question" in html
    assert "Treatment" in html
    assert "Outcome" in html
    assert "Estimated ATE" in html
    assert "CATE status" in html
    assert "Refutation results" in html
    assert "Reviewer warnings" in html
    assert "Caveats / limitations" in html


def test_html_report_escapes_special_characters():
    html = build_html_report(_sample_bundle(question="<script>alert('x')</script>"))

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html
