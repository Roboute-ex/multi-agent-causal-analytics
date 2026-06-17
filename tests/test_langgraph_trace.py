from __future__ import annotations

import pandas as pd
import pytest

from app.core.orchestrator import AnalyticsTeamOrchestrator
from app.core.schemas import AnalysisRequest, PipelineBundle
from app.graph import langgraph_runner
from app.graph.langgraph_runner import (
    LANGGRAPH_NODE_ORDER,
    LangGraphUnavailableError,
    build_graph_state_summary,
    build_trace_step,
    run_langgraph_pipeline_with_trace,
)
from data.generate_synthetic import make_synthetic_marketing_data


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        question="优惠券是否提升购买概率？",
        dataset_path="in_memory.csv",
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )


def test_trace_step_structure_is_stable():
    step = build_trace_step(
        step_name="causal_node",
        status="warning",
        summary="ATE estimation finished.",
        warnings=["fallback estimator used"],
        error=None,
    )

    assert set(step) == {"step_name", "status", "summary", "warnings", "error"}
    assert step["step_name"] == "causal_node"
    assert step["status"] == "warning"
    assert step["warnings"] == ["fallback estimator used"]


def test_graph_state_summary_uses_existing_pipeline_bundle():
    request = _request()
    df = pd.DataFrame({"coupon": [0, 1], "purchase": [0, 1]})
    bundle = PipelineBundle(request=request)
    state = {
        "request": request,
        "df": df,
        "bundle": bundle,
        "errors": [],
        "trace": [
            build_trace_step("coordinator_node", "ok", "Created plan."),
            build_trace_step("data_engineer_node", "ok", "Profiled data."),
        ],
        "state_summary": {},
    }

    summary = build_graph_state_summary(state)

    assert summary["row_count"] == 2
    assert summary["column_count"] == 2
    assert summary["has_profile"] is False
    assert summary["trace_step_count"] == 2
    assert summary["last_step"] == "data_engineer_node"
    assert summary["errors"] == []


def test_langgraph_node_order_documents_linear_workflow():
    assert LANGGRAPH_NODE_ORDER == [
        "coordinator_node",
        "data_engineer_node",
        "statistician_node",
        "causal_node",
        "heterogeneity_node",
        "reviewer_node",
        "reporter_node",
        "deepseek_reporter_node",
    ]


def test_langgraph_trace_optional_when_dependency_missing(monkeypatch):
    monkeypatch.setattr(langgraph_runner, "is_langgraph_available", lambda: False)

    with pytest.raises(LangGraphUnavailableError):
        run_langgraph_pipeline_with_trace(_request(), make_synthetic_marketing_data(n=80, seed=9))


def test_deterministic_pipeline_still_runs_without_langgraph_trace():
    df = make_synthetic_marketing_data(n=120, seed=22)
    bundle = AnalyticsTeamOrchestrator().run_dataframe(_request(), df)

    assert isinstance(bundle, PipelineBundle)
    assert bundle.profile is not None
    assert bundle.estimate is not None
    assert bundle.report_markdown
