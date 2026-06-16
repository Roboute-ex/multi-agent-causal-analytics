from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


HIGH_MISSING_RATE = 0.2
HIGH_CARDINALITY_UNIQUE_COUNT = 50
HIGH_CARDINALITY_RATE = 0.5
TREATMENT_IMBALANCE_MIN_SHARE = 0.1
LOW_COMPLETE_CASE_RATE = 0.8


def run_data_quality_checks(
    df: pd.DataFrame | None,
    treatment: str | None = None,
    outcome: str | None = None,
    confounders: Iterable[str] | None = None,
    effect_modifiers: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Run lightweight data quality checks before causal estimation."""
    confounders = list(confounders or [])
    effect_modifiers = list(effect_modifiers or [])
    warnings: list[str] = []
    recommendations: list[str] = []

    if df is None:
        return {
            "status": "error",
            "summary": {
                "row_count": 0,
                "column_count": 0,
                "dtype_distribution": {},
                "overall_missing_rate": 0.0,
                "duplicate_rows_count": 0,
                "duplicate_rate": 0.0,
            },
            "warnings": ["Dataset is None."],
            "column_quality": [],
            "treatment_quality": _missing_variable_quality(treatment),
            "outcome_quality": _missing_variable_quality(outcome),
            "selected_variables_quality": {
                "selected_variables": _unique_selected_variables(
                    treatment, outcome, confounders, effect_modifiers
                ),
                "missing_columns": [],
                "selected_missingness": {},
                "selected_complete_case_count": 0,
                "selected_complete_case_rate": 0.0,
            },
            "recommendations": ["Load a non-empty dataset before running causal analysis."],
        }

    row_count = int(len(df))
    column_count = int(len(df.columns))
    total_cells = row_count * column_count
    total_missing = int(df.isna().sum().sum()) if column_count else 0
    overall_missing_rate = _rate(total_missing, total_cells)
    duplicate_rows_count = int(df.duplicated().sum()) if row_count else 0
    duplicate_rate = _rate(duplicate_rows_count, row_count)

    if row_count == 0:
        warnings.append("Dataset has no rows.")
        recommendations.append("Load a dataset with at least one row before causal analysis.")
    if column_count == 0:
        warnings.append("Dataset has no columns.")
        recommendations.append("Load a dataset with named columns before causal analysis.")
    if duplicate_rows_count:
        warnings.append(
            f"Dataset contains {duplicate_rows_count} duplicate row(s) "
            f"({duplicate_rate:.1%})."
        )

    column_quality = [_column_quality(df, column, row_count) for column in df.columns]
    high_missingness_columns = [
        item["column"] for item in column_quality if item["missing_rate"] > HIGH_MISSING_RATE
    ]
    constant_columns = [item["column"] for item in column_quality if item["is_constant"]]
    high_cardinality_categorical_columns = [
        item["column"] for item in column_quality if item["high_cardinality"]
    ]
    numeric_summary = {
        item["column"]: item["numeric_summary"]
        for item in column_quality
        if item.get("numeric_summary") is not None
    }
    iqr_outlier_counts = {
        item["column"]: item["iqr_outlier_count"]
        for item in column_quality
        if item["iqr_outlier_count"] is not None
    }

    for column in high_missingness_columns:
        rate_value = _column_missing_rate(column_quality, column)
        warnings.append(f"Column `{column}` has high missingness ({rate_value:.1%}).")
    for column in constant_columns:
        warnings.append(f"Column `{column}` is constant and may not be useful for modeling.")
    for column in high_cardinality_categorical_columns:
        warnings.append(
            f"Column `{column}` is high-cardinality categorical and may need encoding or grouping."
        )

    treatment_quality = _treatment_quality(df, treatment, row_count, warnings, recommendations)
    outcome_quality = _outcome_quality(df, outcome, row_count, warnings, recommendations)
    selected_variables_quality = _selected_variables_quality(
        df=df,
        treatment=treatment,
        outcome=outcome,
        confounders=confounders,
        effect_modifiers=effect_modifiers,
        row_count=row_count,
        warnings=warnings,
        recommendations=recommendations,
    )

    if high_missingness_columns:
        recommendations.append("Review high-missingness columns before interpreting causal results.")
    if constant_columns:
        recommendations.append("Remove or ignore constant columns in causal variable selection.")
    if high_cardinality_categorical_columns:
        recommendations.append("Group or encode high-cardinality categorical columns when needed.")

    summary = {
        "row_count": row_count,
        "column_count": column_count,
        "dtype_distribution": _dtype_distribution(df),
        "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "overall_missing_rate": overall_missing_rate,
        "duplicate_rows_count": duplicate_rows_count,
        "duplicate_rate": duplicate_rate,
        "high_missingness_columns": high_missingness_columns,
        "constant_columns": constant_columns,
        "high_cardinality_categorical_columns": high_cardinality_categorical_columns,
        "numeric_summary": numeric_summary,
        "iqr_outlier_counts": iqr_outlier_counts,
    }

    status = "ok"
    if row_count == 0 or column_count == 0:
        status = "error"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "summary": summary,
        "warnings": warnings,
        "column_quality": column_quality,
        "treatment_quality": treatment_quality,
        "outcome_quality": outcome_quality,
        "selected_variables_quality": selected_variables_quality,
        "recommendations": _dedupe(recommendations),
    }


def _column_quality(df: pd.DataFrame, column: str, row_count: int) -> dict[str, Any]:
    series = df[column]
    missing_count = int(series.isna().sum())
    missing_rate = _rate(missing_count, row_count)
    unique_count = int(series.nunique(dropna=True))
    unique_rate = _rate(unique_count, row_count)
    is_numeric = bool(is_numeric_dtype(series))
    is_categorical = not is_numeric and not is_bool_dtype(series) and not is_datetime64_any_dtype(series)
    is_constant = bool(row_count > 0 and series.nunique(dropna=False) <= 1)
    high_cardinality = bool(
        is_categorical
        and unique_count >= HIGH_CARDINALITY_UNIQUE_COUNT
        and unique_rate >= HIGH_CARDINALITY_RATE
    )
    numeric_summary = _numeric_summary(series) if is_numeric else None

    return {
        "column": column,
        "dtype": str(series.dtype),
        "missing_count": missing_count,
        "missing_rate": missing_rate,
        "unique_count": unique_count,
        "unique_rate": unique_rate,
        "is_constant": is_constant,
        "is_numeric": is_numeric,
        "is_categorical": is_categorical,
        "high_missingness": missing_rate > HIGH_MISSING_RATE,
        "high_cardinality": high_cardinality,
        "numeric_summary": numeric_summary,
        "iqr_outlier_count": _iqr_outlier_count(series) if is_numeric else None,
    }


def _treatment_quality(
    df: pd.DataFrame,
    treatment: str | None,
    row_count: int,
    warnings: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    quality = _missing_variable_quality(treatment)
    if not treatment:
        warnings.append("Treatment column is not selected.")
        recommendations.append("Select a treatment variable before causal estimation.")
        return quality
    if treatment not in df.columns:
        warnings.append(f"Treatment column `{treatment}` is missing from the dataset.")
        recommendations.append("Choose a treatment column that exists in the current dataset.")
        return quality

    series = df[treatment]
    non_missing = series.dropna()
    group_counts = {
        _value_label(key): int(value)
        for key, value in series.value_counts(dropna=False).items()
    }
    non_missing_counts = non_missing.value_counts(dropna=True)
    has_variation = bool(non_missing_counts.size > 1)
    min_group_share = None
    max_group_share = None
    imbalance_warning = False

    if not has_variation:
        warnings.append(f"Treatment `{treatment}` has no variation.")
        recommendations.append("Use a treatment variable with at least two observed groups.")
    elif int(non_missing_counts.sum()) > 0:
        shares = non_missing_counts / non_missing_counts.sum()
        min_group_share = _safe_float(shares.min())
        max_group_share = _safe_float(shares.max())
        imbalance_warning = bool(min_group_share is not None and min_group_share < TREATMENT_IMBALANCE_MIN_SHARE)
        if imbalance_warning:
            warnings.append(
                f"Treatment `{treatment}` is imbalanced; smallest group share is "
                f"{min_group_share:.1%}."
            )
            recommendations.append("Check overlap before interpreting treatment effects.")

    quality.update(
        {
            "exists": True,
            "missing_count": int(series.isna().sum()),
            "missing_rate": _rate(int(series.isna().sum()), row_count),
            "group_counts": group_counts,
            "has_variation": has_variation,
            "min_group_share": min_group_share,
            "max_group_share": max_group_share,
            "imbalance_warning": imbalance_warning,
        }
    )
    return quality


def _outcome_quality(
    df: pd.DataFrame,
    outcome: str | None,
    row_count: int,
    warnings: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    quality = _missing_variable_quality(outcome)
    if not outcome:
        warnings.append("Outcome column is not selected.")
        recommendations.append("Select an outcome variable before causal estimation.")
        return quality
    if outcome not in df.columns:
        warnings.append(f"Outcome column `{outcome}` is missing from the dataset.")
        recommendations.append("Choose an outcome column that exists in the current dataset.")
        return quality

    series = df[outcome]
    missing_count = int(series.isna().sum())
    missing_rate = _rate(missing_count, row_count)
    has_variation = bool(series.dropna().nunique() > 1)
    if not has_variation:
        warnings.append(f"Outcome `{outcome}` has no variation.")
        recommendations.append("Use an outcome variable with meaningful variation.")
    if missing_rate > HIGH_MISSING_RATE:
        warnings.append(f"Outcome `{outcome}` has high missingness ({missing_rate:.1%}).")
        recommendations.append("Review outcome missingness before interpreting ATE or CATE.")

    quality.update(
        {
            "exists": True,
            "missing_count": missing_count,
            "missing_rate": missing_rate,
            "has_variation": has_variation,
            "numeric_summary": _numeric_summary(series) if is_numeric_dtype(series) else None,
        }
    )
    return quality


def _selected_variables_quality(
    df: pd.DataFrame,
    treatment: str | None,
    outcome: str | None,
    confounders: list[str],
    effect_modifiers: list[str],
    row_count: int,
    warnings: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    selected_variables = _unique_selected_variables(treatment, outcome, confounders, effect_modifiers)
    missing_columns = [column for column in selected_variables if column not in df.columns]
    existing_columns = [column for column in selected_variables if column in df.columns]

    for column in missing_columns:
        warnings.append(f"Selected variable `{column}` is missing from the dataset.")

    selected_missingness = {}
    for column in existing_columns:
        missing_count = int(df[column].isna().sum())
        missing_rate = _rate(missing_count, row_count)
        selected_missingness[column] = {
            "missing_count": missing_count,
            "missing_rate": missing_rate,
        }
        if column in confounders and missing_rate > 0:
            warnings.append(f"Confounder `{column}` has missing values ({missing_rate:.1%}).")
            recommendations.append("Consider imputation or complete-case analysis for confounders.")

    if existing_columns:
        selected_complete_case_count = int(df[existing_columns].dropna().shape[0])
    else:
        selected_complete_case_count = row_count if row_count else 0
    selected_complete_case_rate = _rate(selected_complete_case_count, row_count)

    if row_count and selected_complete_case_rate < LOW_COMPLETE_CASE_RATE:
        warnings.append(
            "Selected variables have limited complete cases "
            f"({selected_complete_case_rate:.1%} of rows)."
        )
        recommendations.append("Review missingness in selected causal variables.")

    return {
        "selected_variables": selected_variables,
        "missing_columns": missing_columns,
        "selected_missingness": selected_missingness,
        "selected_complete_case_count": selected_complete_case_count,
        "selected_complete_case_rate": selected_complete_case_rate,
    }


def _missing_variable_quality(column: str | None) -> dict[str, Any]:
    return {
        "column": column,
        "exists": False,
        "missing_count": None,
        "missing_rate": None,
        "has_variation": None,
    }


def _numeric_summary(series: pd.Series) -> dict[str, float | int | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return {
        "min": _safe_float(numeric.min()) if not numeric.empty else None,
        "max": _safe_float(numeric.max()) if not numeric.empty else None,
        "mean": _safe_float(numeric.mean()) if not numeric.empty else None,
        "std": _safe_float(numeric.std()) if len(numeric) > 1 else None,
    }


def _iqr_outlier_count(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric) < 4:
        return 0
    q1 = numeric.quantile(0.25)
    q3 = numeric.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return int(((numeric < lower) | (numeric > upper)).sum())


def _dtype_distribution(df: pd.DataFrame) -> dict[str, int]:
    distribution = {"numeric": 0, "categorical": 0, "boolean": 0, "datetime": 0, "other": 0}
    for column in df.columns:
        series = df[column]
        if is_bool_dtype(series):
            distribution["boolean"] += 1
        elif is_numeric_dtype(series):
            distribution["numeric"] += 1
        elif is_datetime64_any_dtype(series):
            distribution["datetime"] += 1
        elif str(series.dtype) in {"object", "category", "string"}:
            distribution["categorical"] += 1
        else:
            distribution["other"] += 1
    return distribution


def _unique_selected_variables(
    treatment: str | None,
    outcome: str | None,
    confounders: Iterable[str],
    effect_modifiers: Iterable[str],
) -> list[str]:
    selected: list[str] = []
    for column in [treatment, outcome, *confounders, *effect_modifiers]:
        if column and column not in selected:
            selected.append(column)
    return selected


def _column_missing_rate(column_quality: list[dict[str, Any]], column: str) -> float:
    for item in column_quality:
        if item["column"] == column:
            return float(item["missing_rate"])
    return 0.0


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _value_label(value: Any) -> str:
    if pd.isna(value):
        return "<missing>"
    return str(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
