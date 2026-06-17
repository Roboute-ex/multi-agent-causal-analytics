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
    trace: list[dict[str, Any]]
    state_summary: dict[str, Any]


LANGGRAPH_NODE_ORDER = [
    "coordinator_node",
    "data_engineer_node",
    "statistician_node",
    "causal_node",
    "heterogeneity_node",
    "reviewer_node",
    "reporter_node",
    "deepseek_reporter_node",
]


def is_langgraph_available() -> bool:
    return importlib.util.find_spec("langgraph") is not None


def run_langgraph_pipeline(request: AnalysisRequest | dict, df: pd.DataFrame) -> PipelineBundle:
    """Run the existing agent pipeline through an optional LangGraph adapter."""
    bundle, _, _ = run_langgraph_pipeline_with_trace(request, df)
    return bundle


def run_langgraph_pipeline_with_trace(
    request: AnalysisRequest | dict,
    df: pd.DataFrame,
) -> tuple[PipelineBundle, list[dict[str, Any]], dict[str, Any]]:
    """Run the existing agent pipeline and return graph trace metadata for UI display."""
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
        "trace": [],
        "state_summary": {},
    }
    initial_state["state_summary"] = build_graph_state_summary(initial_state)

    coordinator = CoordinatorAgent()
    data_engineer = DataEngineerAgent()
    statistician = StatisticianAgent()
    causal = CausalAgent()
    heterogeneity = HeterogeneityAgent()
    reviewer = ReviewerAgent()
    reporter = ReporterAgent()
    llm_reporter = DeepSeekReporterAgent()

    def coordinator_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = coordinator.run(state["request"])
        bundle.agent_logs.append(result)
        bundle.plan = result.payload
        return _node_update(state, "coordinator_node", result, "Created the fixed causal analytics plan.")

    def data_engineer_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = data_engineer.run(state["df"])
        bundle.agent_logs.append(result)
        bundle.profile = DataProfile(**result.payload)
        summary = f"Profiled {bundle.profile.n_rows} rows and {bundle.profile.n_cols} columns."
        return _node_update(state, "data_engineer_node", result, summary)

    def statistician_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = statistician.run(state["request"], bundle.profile)
        bundle.agent_logs.append(result)
        bundle.method = MethodRecommendation(**result.payload)
        return _node_update(
            state,
            "statistician_node",
            result,
            f"Selected primary method: {bundle.method.primary}.",
        )

    def causal_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = causal.run(state["df"], state["request"])
        bundle.agent_logs.append(result)
        bundle.estimate = EstimationResult(**result.payload)
        return _node_update(
            state,
            "causal_node",
            result,
            f"ATE estimation status: {bundle.estimate.status}; ATE={_format_number(bundle.estimate.ate)}.",
        )

    def heterogeneity_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = heterogeneity.run(state["df"], state["request"])
        bundle.agent_logs.append(result)
        bundle.cate = CateResult(**result.payload)
        return _node_update(
            state,
            "heterogeneity_node",
            result,
            f"CATE analysis status: {bundle.cate.status}.",
        )

    def reviewer_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = reviewer.run(bundle)
        bundle.agent_logs.append(result)
        bundle.review = ReviewResult(**result.payload)
        return _node_update(
            state,
            "reviewer_node",
            result,
            f"Reviewer status: {bundle.review.status}.",
        )

    def reporter_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = reporter.run(bundle)
        bundle.agent_logs.append(result)
        bundle.report_markdown = result.payload["markdown"]
        return _node_update(state, "reporter_node", result, "Generated local Markdown report.")

    def deepseek_reporter_node(state: LangGraphState) -> dict[str, Any]:
        bundle = state["bundle"]
        result = llm_reporter.run(bundle)
        bundle.agent_logs.append(result)
        if result.status == "ok":
            bundle.report_markdown = result.payload["markdown"]
        return _node_update(
            state,
            "deepseek_reporter_node",
            result,
            f"Optional DeepSeek reporter status: {result.status}.",
        )

    graph = StateGraph(LangGraphState)
    graph.add_node("coordinator_node", coordinator_node)
    graph.add_node("data_engineer_node", data_engineer_node)
    graph.add_node("statistician_node", statistician_node)
    graph.add_node("causal_node", causal_node)
    graph.add_node("heterogeneity_node", heterogeneity_node)
    graph.add_node("reviewer_node", reviewer_node)
    graph.add_node("reporter_node", reporter_node)
    graph.add_node("deepseek_reporter_node", deepseek_reporter_node)

    graph.set_entry_point("coordinator_node")
    graph.add_edge("coordinator_node", "data_engineer_node")
    graph.add_edge("data_engineer_node", "statistician_node")
    graph.add_edge("statistician_node", "causal_node")
    graph.add_edge("causal_node", "heterogeneity_node")
    graph.add_edge("heterogeneity_node", "reviewer_node")
    graph.add_edge("reviewer_node", "reporter_node")
    graph.add_edge("reporter_node", "deepseek_reporter_node")
    graph.add_edge("deepseek_reporter_node", END)

    compiled = graph.compile()
    final_state = cast(LangGraphState, compiled.invoke(initial_state))
    bundle = final_state["bundle"]
    trace = final_state["trace"]
    state_summary = final_state["state_summary"]
    bundle.plan["orchestration_mode"] = "langgraph_experimental"
    bundle.plan["langgraph_trace"] = trace
    bundle.plan["langgraph_state_summary"] = state_summary
    return bundle, trace, state_summary


def _coerce_request(request: AnalysisRequest | dict) -> AnalysisRequest:
    if isinstance(request, AnalysisRequest):
        return request
    return AnalysisRequest(**request)


def build_trace_step(
    step_name: str,
    status: str,
    summary: str,
    warnings: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "step_name": step_name,
        "status": status,
        "summary": summary,
        "warnings": warnings or [],
        "error": error,
    }


def build_graph_state_summary(state: LangGraphState) -> dict[str, Any]:
    bundle = state["bundle"]
    df = state["df"]
    trace = state.get("trace", [])
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "has_profile": bundle.profile is not None,
        "has_method": bundle.method is not None,
        "has_estimate": bundle.estimate is not None,
        "has_cate": bundle.cate is not None,
        "has_review": bundle.review is not None,
        "has_report": bool(bundle.report_markdown),
        "agent_log_count": len(bundle.agent_logs),
        "trace_step_count": len(trace),
        "last_step": trace[-1]["step_name"] if trace else None,
        "errors": list(state.get("errors", [])),
    }


def _node_update(
    state: LangGraphState,
    step_name: str,
    result: Any,
    summary: str,
) -> dict[str, Any]:
    warnings = _extract_warnings(result.payload)
    error = result.error or _extract_error(result.payload)
    if error and error not in state["errors"]:
        state["errors"].append(error)
    state["trace"].append(
        build_trace_step(
            step_name=step_name,
            status=result.status,
            summary=summary,
            warnings=warnings,
            error=error,
        )
    )
    state["state_summary"] = build_graph_state_summary(state)
    return {
        "bundle": state["bundle"],
        "errors": state["errors"],
        "trace": state["trace"],
        "state_summary": state["state_summary"],
    }


def _extract_warnings(payload: dict[str, Any]) -> list[str]:
    warnings = payload.get("warnings", [])
    if isinstance(warnings, list):
        return [str(item) for item in warnings if item]
    if warnings:
        return [str(warnings)]
    return []


def _extract_error(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if error:
        return str(error)
    return None


def _format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)
