# v0.7 Advanced LangGraph Orchestration

v0.7 strengthens the optional LangGraph adapter without replacing the deterministic causal analytics pipeline. The stable default path remains `AnalyticsTeamOrchestrator`; LangGraph is still experimental and optional.

## What Changed

- LangGraph execution trace / step timeline for graph runs
- Graph state summary for demo and debugging
- Clear UI explanation that deterministic orchestration remains the stable default
- Lightweight human review checkpoint explanation before execution
- Deployment readiness and public demo safety messaging retained as transitional enhancements

## Graph Nodes

The experimental graph uses a fixed linear workflow:

1. `coordinator_node`
2. `data_engineer_node`
3. `statistician_node`
4. `causal_node`
5. `heterogeneity_node`
6. `reviewer_node`
7. `reporter_node`
8. `deepseek_reporter_node`

There is no dynamic routing, LLM planner, checkpoint persistence, database, or production human-in-the-loop workflow.

## Trace Structure

Each trace step is a plain dictionary:

```text
{
  "step_name": "...",
  "status": "...",
  "summary": "...",
  "warnings": [...],
  "error": null
}
```

The graph state summary is also a plain dictionary. It contains high-level flags such as whether profile, method, estimate, CATE, review, report, and trace steps are available. It does not store uploaded data.

## Optional Dependency Boundary

LangGraph remains optional:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-langgraph.txt
```

If `langgraph` is unavailable, Streamlit falls back to the deterministic orchestrator and does not crash.

## Human Review Boundary

The human review checkpoint is demo-safe and UI-level only. It displays the selected treatment, outcome, confounders, and effect modifiers before execution. It does not store approvals, persist uploaded data, or implement production HITL.
