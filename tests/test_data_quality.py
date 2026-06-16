from __future__ import annotations

import pandas as pd
import pytest

from app.services.data_quality import run_data_quality_checks


def _column(result: dict, name: str) -> dict:
    return next(item for item in result["column_quality"] if item["column"] == name)


def test_basic_data_quality_dict_generates():
    df = pd.DataFrame(
        {
            "coupon": [0, 1, 0, 1],
            "purchase": [0, 1, 0, 1],
            "age": [20, 30, 40, 50],
            "visits": [1, 2, 3, 4],
        }
    )

    result = run_data_quality_checks(
        df,
        treatment="coupon",
        outcome="purchase",
        confounders=["age"],
        effect_modifiers=["visits"],
    )

    assert result["status"] == "ok"
    assert result["summary"]["row_count"] == 4
    assert result["summary"]["column_count"] == 4
    assert result["summary"]["dtype_distribution"]["numeric"] == 4
    assert result["column_quality"]


def test_missing_rate_calculation_is_correct():
    df = pd.DataFrame({"coupon": [0, 1, 0, 1], "purchase": [1, None, 0, None]})

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert _column(result, "purchase")["missing_count"] == 2
    assert _column(result, "purchase")["missing_rate"] == pytest.approx(0.5)
    assert result["summary"]["overall_missing_rate"] == pytest.approx(0.25)


def test_duplicate_rows_are_counted():
    df = pd.DataFrame(
        {
            "coupon": [0, 0, 1],
            "purchase": [1, 1, 0],
            "age": [30, 30, 40],
        }
    )

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["summary"]["duplicate_rows_count"] == 1
    assert result["summary"]["duplicate_rate"] == pytest.approx(1 / 3)


def test_constant_columns_are_identified():
    df = pd.DataFrame(
        {
            "coupon": [0, 1, 0, 1],
            "purchase": [0, 1, 0, 1],
            "constant_feature": [7, 7, 7, 7],
        }
    )

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert "constant_feature" in result["summary"]["constant_columns"]
    assert any("constant_feature" in warning for warning in result["warnings"])


def test_high_cardinality_categorical_columns_are_identified():
    df = pd.DataFrame(
        {
            "coupon": [0, 1] * 30,
            "purchase": [0, 1] * 30,
            "user_segment": [f"segment_{index}" for index in range(60)],
        }
    )

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert "user_segment" in result["summary"]["high_cardinality_categorical_columns"]
    assert _column(result, "user_segment")["high_cardinality"] is True


def test_treatment_group_counts_are_calculated():
    df = pd.DataFrame({"coupon": [0, 0, 0, 1, 1], "purchase": [0, 1, 0, 1, 1]})

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["treatment_quality"]["group_counts"] == {"0": 3, "1": 2}
    assert result["treatment_quality"]["has_variation"] is True


def test_treatment_imbalance_adds_warning():
    df = pd.DataFrame(
        {
            "coupon": [0] * 95 + [1] * 5,
            "purchase": [0, 1] * 50,
        }
    )

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["treatment_quality"]["imbalance_warning"] is True
    assert any("imbalanced" in warning for warning in result["warnings"])


def test_treatment_without_variation_adds_warning():
    df = pd.DataFrame({"coupon": [1, 1, 1], "purchase": [0, 1, 0]})

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["treatment_quality"]["has_variation"] is False
    assert any("Treatment `coupon` has no variation" in warning for warning in result["warnings"])


def test_outcome_missing_rate_is_calculated():
    df = pd.DataFrame({"coupon": [0, 1, 0, 1], "purchase": [1, None, 0, 1]})

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["outcome_quality"]["missing_count"] == 1
    assert result["outcome_quality"]["missing_rate"] == pytest.approx(0.25)


def test_outcome_without_variation_adds_warning():
    df = pd.DataFrame({"coupon": [0, 1, 0, 1], "purchase": [1, 1, 1, 1]})

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase")

    assert result["outcome_quality"]["has_variation"] is False
    assert any("Outcome `purchase` has no variation" in warning for warning in result["warnings"])


def test_selected_complete_case_count_is_correct():
    df = pd.DataFrame(
        {
            "coupon": [0, 1, 0, 1],
            "purchase": [1, 0, 1, None],
            "age": [20, None, 40, 50],
            "visits": [1, 2, 3, 4],
        }
    )

    result = run_data_quality_checks(
        df,
        treatment="coupon",
        outcome="purchase",
        confounders=["age"],
        effect_modifiers=["visits"],
    )

    selected_quality = result["selected_variables_quality"]
    assert selected_quality["selected_complete_case_count"] == 2
    assert selected_quality["selected_complete_case_rate"] == pytest.approx(0.5)


def test_confounder_missingness_adds_warning():
    df = pd.DataFrame(
        {
            "coupon": [0, 1, 0],
            "purchase": [1, 0, 1],
            "age": [20, None, 40],
        }
    )

    result = run_data_quality_checks(df, treatment="coupon", outcome="purchase", confounders=["age"])

    assert result["selected_variables_quality"]["selected_missingness"]["age"]["missing_count"] == 1
    assert any("Confounder `age` has missing values" in warning for warning in result["warnings"])


def test_empty_data_is_handled_gracefully():
    result = run_data_quality_checks(pd.DataFrame(), treatment="coupon", outcome="purchase")

    assert result["status"] == "error"
    assert result["summary"]["row_count"] == 0
    assert result["summary"]["column_count"] == 0
    assert result["warnings"]


def test_missing_selected_columns_are_handled_gracefully():
    df = pd.DataFrame({"purchase": [0, 1, 0], "age": [20, 30, 40]})

    result = run_data_quality_checks(
        df,
        treatment="coupon",
        outcome="missing_outcome",
        confounders=["missing_confounder"],
    )

    assert result["treatment_quality"]["exists"] is False
    assert result["outcome_quality"]["exists"] is False
    assert "coupon" in result["selected_variables_quality"]["missing_columns"]
    assert "missing_outcome" in result["selected_variables_quality"]["missing_columns"]
    assert "missing_confounder" in result["selected_variables_quality"]["missing_columns"]
