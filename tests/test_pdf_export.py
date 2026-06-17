from __future__ import annotations

import importlib

import pytest

from app.core.pdf_export import (
    PDFExportUnavailableError,
    build_pdf_report,
    is_pdf_export_available,
)
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


def _sample_bundle() -> PipelineBundle:
    return PipelineBundle(
        request=AnalysisRequest(
            question="优惠券是否提升购买率？",
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
                }
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
        },
        "warnings": ["Outcome missingness should be reviewed."],
        "treatment_quality": {
            "group_counts": {"0": 60, "1": 60},
        },
        "outcome_quality": {
            "missing_rate": 0.05,
        },
        "selected_variables_quality": {
            "selected_complete_case_count": 112,
        },
    }


def test_pdf_export_module_imports_without_required_dependency():
    module = importlib.import_module("app.core.pdf_export")

    assert hasattr(module, "PDFExportUnavailableError")
    assert hasattr(module, "is_pdf_export_available")
    assert hasattr(module, "build_pdf_report")


def test_is_pdf_export_available_returns_bool():
    assert isinstance(is_pdf_export_available(), bool)


def test_build_pdf_report_raises_clear_error_when_unavailable(monkeypatch):
    import app.core.pdf_export as pdf_export

    monkeypatch.setattr(pdf_export, "is_pdf_export_available", lambda: False)

    with pytest.raises(PDFExportUnavailableError, match="Optional PDF export requires reportlab"):
        pdf_export.build_pdf_report(_sample_bundle(), data_quality=_sample_data_quality())


def test_build_pdf_report_returns_pdf_bytes_when_reportlab_available():
    if not is_pdf_export_available():
        pytest.skip("reportlab is not installed; PDF bytes generation is optional.")

    pdf_bytes = build_pdf_report(_sample_bundle(), data_quality=_sample_data_quality())

    assert isinstance(pdf_bytes, bytes)
    assert b"%PDF" in pdf_bytes[:20]
