# AGENTS.md

## Project Overview

Project name: Multi-Agent Causal Analytics Team

This repository is a local, GitHub-ready MVP for a multi-agent causal analytics workflow. The project uses a deterministic agent pipeline to complete causal data analysis, including:

- data profiling
- method selection
- ATE estimation
- optional CATE analysis with graceful skip
- data quality checks before causal analysis
- optional LangGraph orchestration adapter with graceful fallback
- polished HTML and optional PDF report export
- deployment readiness and public demo safety messaging
- causal trust, sensitivity, and heterogeneity explanation summaries
- refutation checks
- Reviewer Agent validation
- Markdown report generation

Current project status:

- Phase 1 MVP is complete.
- Phase 2 presentation enhancement is complete.
- The latest full pytest result should be checked after each change; v0.8 focuses on Causal Robustness and Interpretability while preserving the deterministic pipeline.
- Streamlit can be accessed locally.
- The current priority is stability, GitHub presentation quality, and resume presentation quality.

## Repository Layout

- `app/ui_streamlit.py`: Streamlit UI entrypoint and demo-facing presentation layer.
- `app/core/orchestrator.py`: deterministic multi-agent pipeline orchestration.
- `app/core/schemas.py`: Pydantic request/result schemas shared across agents and services.
- `app/core/report.py`: local Markdown report generation.
- `app/core/report_export.py`: local HTML report export generated after the pipeline finishes.
- `app/core/pdf_export.py`: optional ReportLab PDF export generated after the pipeline finishes.
- `app/graph/langgraph_runner.py`: optional LangGraph experimental orchestration adapter.
- `app/agents/team.py`: core agents, including Data Engineer, Statistician, Causal Agent, Heterogeneity Agent, Reviewer, and Reporter.
- `app/services/data_quality.py`: lightweight data quality checks returned as a plain dict for UI/report display.
- `app/services/dependency_status.py`: deployment-safe optional dependency and API configuration status.
- `app/services/causal_trust.py`: v0.8 plain-dict causal trust summary built from ATE, refutations, reviewer warnings, data quality, sensitivity, and heterogeneity signals.
- `app/services/sensitivity_service.py`: v0.8 conservative robustness/sensitivity summary wrapper built from existing refutation results.
- `app/services/heterogeneity_explainer.py`: v0.8 optional CATE explanation helper with graceful skip behavior.
- `app/services/causal_dowhy.py`: DoWhy ATE estimation and fallback linear adjustment logic.
- `app/services/cate_econml.py`: optional EconML CATE analysis with graceful skip behavior.
- `data/generate_synthetic.py`: synthetic marketing sample data generator.
- `data/sample_marketing.csv`: built-in sample dataset for demos and tests.
- `tests/`: pytest coverage for the pipeline, data loading, optional CATE skip, and refutation behavior.

## Development Rules

- Do not large-scale rewrite this project.
- Do not delete old files unless the user explicitly approves it.
- Do not force-install EconML or move it into the base requirements.
- Do not enable DeepSeek / LLM reporting by default.
- Do not make LLM-assisted variable recommendation part of the required deterministic MVP flow.
- Do not integrate the OpenAI API unless the user explicitly requests it.
- Keep LangGraph optional and experimental; do not replace `app/core/orchestrator.py`.
- Do not move LangGraph into base requirements.
- Keep LangGraph trace/state summary as plain dict metadata; do not add Pydantic schemas for it unless explicitly requested.
- Keep ReportLab PDF export optional; do not move it into base requirements.
- Do not add a database, login system, or deployment configuration unless the user explicitly requests it.
- Do not read, print, upload, or commit `.env`.
- Do not commit `.streamlit/secrets.toml`.
- Do not commit private data under `data/raw/`, `data/prepared/`, or local `scripts/`.
- Do not run `git push`.
- Preserve the current MVP behavior before adding presentation or documentation improvements.
- Keep report export as a presentation/download layer; do not make it part of the causal pipeline.
- Keep PDF export as a presentation/download layer; do not make it part of the causal pipeline.
- Keep data quality checks as pre-analysis diagnostics and report/UI display; do not make them change ATE/CATE/refutation computation.
- Keep v0.8 trust, sensitivity, and heterogeneity explanation modules as presentation/interpretability helpers; do not make them alter ATE/CATE/refutation computation.
- Keep v0.8 service outputs as plain dicts unless the user explicitly asks for schema changes.
- Do not overstate causal conclusions; summaries must mention observational data limitations, confounding risk, and sample quality risk where relevant.
- Keep LangGraph as orchestration only; do not add new statistical estimation logic inside graph nodes.
- Do not add LangGraph checkpoint, persistence, human-in-the-loop, dynamic routing, or LLM planner unless explicitly requested.
- Lightweight human review checkpoints should stay demo/UI-level only and must not store approvals or uploaded data.
- Keep deployment readiness lightweight; do not add login, database, persistent uploaded data storage, Docker, Kubernetes, or production access control unless explicitly requested.
- Do not add matplotlib, seaborn, or plotly for v0.4-style lightweight charts; prefer pandas and Streamlit built-ins.
- Prefer small, targeted edits that keep the existing repository layout intact.

## Commands

Generate sample data:

```powershell
python data/generate_synthetic.py
```

Run tests:

```powershell
python -m pytest -q
```

Start Streamlit:

```powershell
streamlit run app/ui_streamlit.py
```

Windows virtual environment examples:

```powershell
.\.venv\Scripts\python.exe data\generate_synthetic.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\streamlit.exe run app\ui_streamlit.py
.\.venv\Scripts\python.exe -m pip install -r requirements-langgraph.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-pdf.txt
```

## Testing Requirements

- After changing core logic, run `python -m pytest -q`.
- After changing `app/ui_streamlit.py`, run at least:

```powershell
python -m py_compile app/ui_streamlit.py
```

- CATE optional skip must not break the main ATE, Reviewer, and Reporter pipeline.
- DeepSeek is optional and must not be required for MVP tests.
- LLM-assisted variable recommendation is optional and must gracefully skip or fallback when API access or JSON parsing fails.
- DoWhy can fall back when unavailable, but fallback behavior must include a warning.
- Keep `requirements-cate.txt` separate from base dependencies.
- HTML report export must not introduce required dependencies; PDF export should remain optional unless explicitly requested.
- PDF export must gracefully skip or raise `PDFExportUnavailableError` when ReportLab is unavailable.
- Data Quality checks should return a plain dict unless the user explicitly asks for schema changes.
- LangGraph tests must skip full-run behavior when `langgraph` is not installed rather than failing.
- LangGraph trace tests should validate stable metadata shape without requiring `langgraph` to be installed.
- Dependency status checks must not expose API key values.
- Public demo UI should remind users to use sample data and avoid private or sensitive uploads.
- Causal trust, sensitivity, and heterogeneity explanation tests should not require DeepSeek, EconML, SHAP, LangGraph, or ReportLab.

## Definition of Done

A change is done only when:

- pytest passes when relevant to the change.
- Streamlit can start when UI behavior is changed.
- README and documentation remain consistent with the code.
- no unnecessary dependency is introduced.
- no MVP feature is broken.
- optional EconML and DeepSeek paths remain optional.
- optional LLM variable recommendation never blocks manual variable selection or causal analysis.
- v0.8 interpretability summaries remain optional display/report layers and do not mutate the deterministic pipeline result.
- sensitive local files such as `.env` are not read or exposed.
