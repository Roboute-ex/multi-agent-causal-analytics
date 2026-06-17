from __future__ import annotations

from app.core.report import build_data_quality_markdown, build_markdown_report
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


def _sample_data_quality() -> dict:
    return {
        "status": "warning",
        "summary": {
            "row_count": 120,
            "column_count": 5,
            "overall_missing_rate": 0.02,
            "duplicate_rows_count": 1,
            "duplicate_rate": 1 / 120,
            "high_missingness_columns": ["<script>bad_column</script>"],
        },
        "warnings": ["Check <script>alert('x')</script> before interpretation."],
        "column_quality": [],
        "treatment_quality": {
            "column": "coupon",
            "exists": True,
            "missing_rate": 0.0,
            "has_variation": True,
            "group_counts": {"0": 60, "1": 60},
            "imbalance_warning": False,
        },
        "outcome_quality": {
            "column": "purchase",
            "exists": True,
            "missing_rate": 0.05,
            "has_variation": True,
        },
        "selected_variables_quality": {
            "selected_variables": ["coupon", "purchase", "age"],
            "missing_columns": [],
            "selected_missingness": {
                "coupon": {"missing_count": 0, "missing_rate": 0.0},
                "purchase": {"missing_count": 6, "missing_rate": 0.05},
                "age": {"missing_count": 2, "missing_rate": 0.0167},
            },
            "selected_complete_case_count": 112,
            "selected_complete_case_rate": 112 / 120,
        },
        "recommendations": ["Review selected variable missingness."],
    }


def test_markdown_report_still_generates():
    markdown = build_markdown_report(_sample_bundle())

    assert markdown
    assert "Multi-Agent Causal Analytics Team Report" in markdown


def test_html_report_generates_core_sections():
    html = build_html_report(_sample_bundle())

    assert html
    assert "Multi-Agent Causal Analytics Team Report" in html
    assert "Report summary cards" in html
    assert "summary-card" in html
    assert "User question" in html
    assert "Treatment" in html
    assert "Outcome" in html
    assert "Estimated ATE" in html
    assert "CATE status" in html
    assert "Refutation results" in html
    assert "Reviewer warnings" in html
    assert "Caveats / limitations" in html


def test_html_report_has_professional_header_and_print_css():
    html = build_html_report(_sample_bundle())

    assert 'class="report-header"' in html
    assert "A polished causal analytics report" in html
    assert "@media print" in html


def test_html_report_escapes_special_characters():
    html = build_html_report(_sample_bundle(question="<script>alert('x')</script>"))

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_html_report_with_data_quality_contains_summary():
    html = build_html_report(_sample_bundle(), data_quality=_sample_data_quality())

    assert "Data Quality Summary" in html
    assert "Missingness Overview" in html
    assert "Treatment Balance" in html
    assert "Outcome Quality" in html
    assert "Selected Variables Quality" in html
    assert "Causal Readiness Warnings" in html
    assert "<script>bad_column</script>" not in html
    assert "&lt;script&gt;bad_column&lt;/script&gt;" in html


def test_html_report_without_data_quality_keeps_previous_behavior():
    html = build_html_report(_sample_bundle(), data_quality=None)

    assert "Multi-Agent Causal Analytics Team Report" in html
    assert "Data Quality Summary" not in html


def test_markdown_data_quality_helper_contains_summary():
    markdown = build_data_quality_markdown(_sample_data_quality())

    assert "Data Quality Summary" in markdown
    assert "Missingness Overview" in markdown
    assert "Treatment Balance" in markdown
    assert "Causal Readiness Warnings" in markdown


def test_markdown_data_quality_helper_handles_empty_warnings():
    data_quality = _sample_data_quality()
    data_quality["warnings"] = []

    markdown = build_data_quality_markdown(data_quality)

    assert "No major data quality warnings." in markdown
