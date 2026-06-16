from __future__ import annotations

import importlib.util
from typing import Any, TypedDict, cast

import pandas as pd

from app.agents.llm_reporter import DeepSeekReporterAgent
from app.agents.team import (
    CausalAgent,
    CoordinatorAgent,
    DataEngineerAgent,
    HeterogeneityAgent,
    ReporterAgent,
    ReviewerAgent,
    StatisticianAgent,
)
from app.core.schemas import (
    AnalysisRequest,
    CateResult,
    DataProfile,
    EstimationResult,
    MethodRecommendation,
    PipelineBundle,
    ReviewResult,
)


class LangGraphUnavailableError(RuntimeError):
    """Raised when the optional LangGraph dependency is not installed."""


class LangGraphState(TypedDict):
    request: AnalysisRequest
    df: pd.DataFrame
    bundle: PipelineBundle
    errors: list[str]


def is_langgraph_available() -> bool:
    return importlib.util.find_spec("langgraph") is not None


def run_langgraph_pipeline(request: AnalysisRequest | dict, df: pd.DataFrame) -> PipelineBundle:
    """Run the existing agent pipeline through an optional LangGraph adapter."""
    if not is_langgraph_available():
        raise LangGraphUnavailableError(
            "LangGraph is not installed. Install requirements-langgraph.txt to enable this mode."
        )

    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise LangGraphUnavailableError(
            "LangGraph is installed but its graph API could not be imported."
        ) from exc

    parsed_request = _coerce_request(request)
    initial_state: LangGraphState = {
        "request": parsed_request,
        "df": df,
        "bundle": PipelineBundle(request=parsed_request),
        "errors": [],
    }

    coordinator = CoordinatorAgent()
    data_engineer = DataEngineerAgent()
    statistician = StatisticianAgent()
    causal = CausalAgent()
    heterogeneity = HeterogeneityAgent()
    reviewer = ReviewerAgent()
    reporter = ReporterAgent()
    llm_reporter = DeepSeekReporterAgent()

    def coordinator_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = coordinator.run(state["request"])
        bundle.agent_logs.append(result)
        bundle.plan = result.payload
        return {"bundle": bundle}

    def data_engineer_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = data_engineer.run(state["df"])
        bundle.agent_logs.append(result)
        bundle.profile = DataProfile(**result.payload)
        return {"bundle": bundle}

    def statistician_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = statistician.run(state["request"], bundle.profile)
        bundle.agent_logs.append(result)
        bundle.method = MethodRecommendation(**result.payload)
        return {"bundle": bundle}

    def causal_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = causal.run(state["df"], state["request"])
        bundle.agent_logs.append(result)
        bundle.estimate = EstimationResult(**result.payload)
        return {"bundle": bundle}

    def heterogeneity_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = heterogeneity.run(state["df"], state["request"])
        bundle.agent_logs.append(result)
        bundle.cate = CateResult(**result.payload)
        return {"bundle": bundle}

    def reviewer_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = reviewer.run(bundle)
        bundle.agent_logs.append(result)
        bundle.review = ReviewResult(**result.payload)
        return {"bundle": bundle}

    def reporter_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = reporter.run(bundle)
        bundle.agent_logs.append(result)
        bundle.report_markdown = result.payload["markdown"]
        return {"bundle": bundle}

    def deepseek_reporter_node(state: LangGraphState) -> dict[str, PipelineBundle]:
        bundle = state["bundle"]
        result = llm_reporter.run(bundle)
        bundle.agent_logs.append(result)
        if result.status == "ok":
            bundle.report_markdown = result.payload["markdown"]
        return {"bundle": bundle}

    graph = StateGraph(LangGraphState)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("data_engineer", data_engineer_node)
    graph.add_node("statistician", statistician_node)
    graph.add_node("causal", causal_node)
    graph.add_node("heterogeneity", heterogeneity_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("deepseek_reporter", deepseek_reporter_node)

    graph.set_entry_point("coordinator")
    graph.add_edge("coordinator", "data_engineer")
    graph.add_edge("data_engineer", "statistician")
    graph.add_edge("statistician", "causal")
    graph.add_edge("causal", "heterogeneity")
    graph.add_edge("heterogeneity", "reviewer")
    graph.add_edge("reviewer", "reporter")
    graph.add_edge("reporter", "deepseek_reporter")
    graph.add_edge("deepseek_reporter", END)

    compiled = graph.compile()
    final_state = cast(LangGraphState, compiled.invoke(initial_state))
    return final_state["bundle"]


def _coerce_request(request: AnalysisRequest | dict) -> AnalysisRequest:
    if isinstance(request, AnalysisRequest):
        return request
    return AnalysisRequest(**request)
