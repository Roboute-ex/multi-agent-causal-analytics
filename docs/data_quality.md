# Data Quality Checks

v0.4 adds lightweight data quality diagnostics before causal analysis. The goal is to make data risks visible without changing the deterministic ATE, CATE, refutation, Reviewer, or report pipeline.

## What It Checks

- Basic shape: row count, column count, dtype distribution
- Missingness: per-column missing count/rate and overall missing rate
- Duplicate rows and duplicate rate
- Constant columns
- High-cardinality categorical columns
- Numeric summary: min, max, mean, std
- Simple IQR outlier count
- Treatment existence, group counts, variation, and imbalance
- Outcome existence, variation, and missing rate
- Selected variable missingness and selected complete-case count
- Confounder missingness warnings

## Where It Appears

- Streamlit UI: shown after variable selection and before running causal analysis
- Markdown report: appended in the Streamlit download content
- HTML report: rendered when `build_html_report(..., data_quality=data_quality)` receives the optional dict

## Design Boundary

Data Quality Checks are diagnostics only. They do not automatically clean data, drop rows, change selected variables, or alter causal estimates.
