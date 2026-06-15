# AGENTS.md

## Project Overview

Project name: Multi-Agent Causal Analytics Team

This repository is a local, GitHub-ready MVP for a multi-agent causal analytics workflow. The project uses a deterministic agent pipeline to complete causal data analysis, including:

- data profiling
- method selection
- ATE estimation
- optional CATE analysis with graceful skip
- refutation checks
- Reviewer Agent validation
- Markdown report generation

Current project status:

- Phase 1 MVP is complete.
- Phase 2 presentation enhancement is complete.
- The latest pytest result was `7 passed`.
- Streamlit can be accessed locally.
- The current priority is stability, GitHub presentation quality, and resume presentation quality.

## Repository Layout

- `app/ui_streamlit.py`: Streamlit UI entrypoint and demo-facing presentation layer.
- `app/core/orchestrator.py`: deterministic multi-agent pipeline orchestration.
- `app/core/schemas.py`: Pydantic request/result schemas shared across agents and services.
- `app/core/report.py`: local Markdown report generation.
- `app/agents/team.py`: core agents, including Data Engineer, Statistician, Causal Agent, Heterogeneity Agent, Reviewer, and Reporter.
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
- Do not integrate the OpenAI API unless the user explicitly requests it.
- Do not integrate LangGraph unless the user explicitly requests it.
- Do not add a database, login system, or deployment configuration unless the user explicitly requests it.
- Do not read, print, upload, or commit `.env`.
- Do not run `git push`.
- Preserve the current MVP behavior before adding presentation or documentation improvements.
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
```

## Testing Requirements

- After changing core logic, run `python -m pytest -q`.
- After changing `app/ui_streamlit.py`, run at least:

```powershell
python -m py_compile app/ui_streamlit.py
```

- CATE optional skip must not break the main ATE, Reviewer, and Reporter pipeline.
- DeepSeek is optional and must not be required for MVP tests.
- DoWhy can fall back when unavailable, but fallback behavior must include a warning.
- Keep `requirements-cate.txt` separate from base dependencies.

## Definition of Done

A change is done only when:

- pytest passes when relevant to the change.
- Streamlit can start when UI behavior is changed.
- README and documentation remain consistent with the code.
- no unnecessary dependency is introduced.
- no MVP feature is broken.
- optional EconML and DeepSeek paths remain optional.
- sensitive local files such as `.env` are not read or exposed.

