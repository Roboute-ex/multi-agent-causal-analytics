from __future__ import annotations

import importlib
import inspect
from numbers import Real

import pytest

from app.core.schemas import AnalysisRequest, PipelineBundle
from app.graph import langgraph_runner
from app.graph.langgraph_runner import (
    LANGGRAPH_NODE_ORDER,
    LangGraphUnavailableError,
    run_langgraph_pipeline,
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


def test_langgraph_runner_imports_without_optional_dependency():
    module = importlib.import_module("app.graph.langgraph_runner")

    assert hasattr(module, "is_langgraph_available")
    assert hasattr(module, "run_langgraph_pipeline")
    assert hasattr(module, "run_langgraph_pipeline_with_trace")
    assert hasattr(module, "LangGraphUnavailableError")


def test_is_langgraph_available_returns_false_when_missing(monkeypatch):
    original_find_spec = langgraph_runner.importlib.util.find_spec

    def fake_find_spec(name: str):
        if name == "langgraph":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(langgraph_runner.importlib.util, "find_spec", fake_find_spec)

    assert langgraph_runner.is_langgraph_available() is False


def test_run_langgraph_pipeline_raises_clear_error_when_missing(monkeypatch):
    monkeypatch.setattr(langgraph_runner, "is_langgraph_available", lambda: False)

    with pytest.raises(LangGraphUnavailableError, match="LangGraph is not installed"):
        run_langgraph_pipeline(_request(), make_synthetic_marketing_data(n=80, seed=7))


def test_run_langgraph_pipeline_with_trace_raises_clear_error_when_missing(monkeypatch):
    monkeypatch.setattr(langgraph_runner, "is_langgraph_available", lambda: False)

    with pytest.raises(LangGraphUnavailableError, match="LangGraph is not installed"):
        run_langgraph_pipeline_with_trace(_request(), make_synthetic_marketing_data(n=80, seed=7))


def test_langgraph_runner_does_not_import_openai_api():
    source = inspect.getsource(langgraph_runner).lower()

    assert "openai" not in source


def test_run_langgraph_pipeline_returns_pipeline_bundle_when_installed():
    if not langgraph_runner.is_langgraph_available():
        pytest.skip("langgraph is not installed; full LangGraph run is optional.")

    df = make_synthetic_marketing_data(n=300, seed=123)
    bundle = run_langgraph_pipeline(_request(), df)

    assert isinstance(bundle, PipelineBundle)
    assert bundle.profile is not None
    assert bundle.method is not None
    assert bundle.estimate is not None
    assert bundle.estimate.status == "ok"
    assert isinstance(bundle.estimate.ate, Real)
    assert bundle.cate is not None
    assert bundle.cate.status in {"ok", "skipped", "error"}
    assert bundle.review is not None
    assert bundle.report_markdown
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


def test_run_langgraph_pipeline_with_trace_returns_trace_when_installed():
    if not langgraph_runner.is_langgraph_available():
        pytest.skip("langgraph is not installed; full LangGraph run is optional.")

    df = make_synthetic_marketing_data(n=300, seed=456)
    bundle, trace, state_summary = run_langgraph_pipeline_with_trace(_request(), df)

    assert isinstance(bundle, PipelineBundle)
    assert [step["step_name"] for step in trace] == LANGGRAPH_NODE_ORDER
    assert state_summary["trace_step_count"] == len(LANGGRAPH_NODE_ORDER)
    assert state_summary["has_report"] is True
    assert bundle.plan["langgraph_trace"] == trace
