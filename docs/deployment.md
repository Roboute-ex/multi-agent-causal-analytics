# Deployment Guide

This project is suitable for a lightweight Streamlit public demo. Public deployments should use the built-in sample dataset and should not receive private, sensitive, or real business data.

## Local Demo Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app\ui_streamlit.py
```

Open:

```text
http://localhost:8501
```

For public demo messaging, set:

```powershell
$env:APP_DEMO_MODE="true"
```

## Streamlit Community Cloud Checklist

- Repository entrypoint: `app/ui_streamlit.py`
- Basic dependency file: `requirements.txt`
- Use the built-in sample dataset: `data/sample_marketing.csv`
- Do not commit private datasets or local cleaning scripts.
- Configure secrets through the Streamlit Cloud secrets UI when needed.
- Keep optional dependencies optional unless the demo explicitly needs them.

## Optional Dependency Files

- `requirements-causal.txt`: DoWhy causal estimation and refutation API
- `requirements-cate.txt`: EconML CATE analysis
- `requirements-langgraph.txt`: LangGraph experimental orchestration adapter
- `requirements-pdf.txt`: ReportLab PDF export

The app is designed to continue running when optional dependencies are unavailable.

## Secrets Policy

- Do not commit `.env`.
- Do not commit `.streamlit/secrets.toml`.
- Do not print API keys in logs or UI.
- Use Streamlit Cloud secrets for `DEEPSEEK_API_KEY` if optional LLM features are enabled.

## Data Safety Policy

- Do not commit `data/raw/`.
- Do not commit `data/prepared/`.
- Do not commit local temporary scripts under `scripts/`.
- Public demos should use `data/sample_marketing.csv`.
- Do not upload private, sensitive, or real business data to public deployments.

## Deployment Limitations

- No login system.
- No database.
- No persistent uploaded data.
- No production access control.
- Not suitable for private business data in a public deployment.
- Causal results still depend on user-selected variables and assumptions.
