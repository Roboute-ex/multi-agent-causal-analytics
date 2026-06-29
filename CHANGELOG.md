# Changelog

All notable changes for the Multi-Agent Causal Analytics Team are documented here.

## v0.8 - Causal Robustness and Interpretability

### Added

- Added `app/services/causal_trust.py` to summarize causal result trust using ATE, refutations, reviewer warnings, data quality warnings, sensitivity notes, and heterogeneity signals.
- Added `app/services/sensitivity_service.py` as a conservative wrapper around existing refutation results.
- Added `app/services/heterogeneity_explainer.py` to translate optional CATE output into business-facing heterogeneity notes.
- Added Streamlit expanders for Causal Trust Summary, Robustness / Sensitivity Notes, and Heterogeneity Explanation.
- Added Markdown, HTML, and optional PDF report sections for v0.8 interpretability summaries.
- Added release documentation in `docs/releases/v0.8.md`.

### Testing

- Added unit tests for causal trust, sensitivity summary, and heterogeneity explanation services.
- Extended report export tests for v0.8 section presence and HTML escaping.
- Extended optional PDF export tests to ensure new summary parameters do not break graceful fallback.

### Notes

- No forced dependency was added.
- No OpenAI API, database, login, deployment system, or data persistence was added.
- The deterministic causal pipeline remains the default stable path.
- Core ATE/CATE/refutation logic was not changed.

