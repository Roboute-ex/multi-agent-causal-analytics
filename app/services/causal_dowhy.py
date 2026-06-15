from __future__ import annotations

import re
from typing import Any, List

import numpy as np
import pandas as pd

from app.core.schemas import EstimationResult


def build_dot_graph(
    treatment: str,
    outcome: str,
    confounders: List[str],
    effect_modifiers: List[str] | None = None,
) -> str:
    modifiers = effect_modifiers or []
    lines = ["digraph {"]
    for confounder in confounders:
        lines.append(f'    "{confounder}" -> "{treatment}";')
        lines.append(f'    "{confounder}" -> "{outcome}";')
    for modifier in modifiers:
        if modifier not in confounders:
            lines.append(f'    "{modifier}" -> "{outcome}";')
    lines.append(f'    "{treatment}" -> "{outcome}";')
    lines.append("}")
    return "\n".join(lines)


def estimate_ate(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
    effect_modifiers: List[str] | None = None,
) -> EstimationResult:
    graph_dot = build_dot_graph(treatment, outcome, confounders, effect_modifiers)
    try:
        return _estimate_with_dowhy(df, treatment, outcome, confounders, graph_dot)
    except ImportError as exc:
        fallback = _estimate_with_numpy(df, treatment, outcome, confounders, graph_dot)
        fallback.warnings.append(f"未安装 DoWhy，已使用降级估计器：{exc}")
        return fallback
    except Exception as exc:
        fallback = _estimate_with_numpy(df, treatment, outcome, confounders, graph_dot)
        fallback.warnings.append(f"DoWhy 运行失败，已使用降级估计器：{exc}")
        return fallback


def _estimate_with_dowhy(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
    graph_dot: str,
) -> EstimationResult:
    from dowhy import CausalModel

    model = CausalModel(
        data=df,
        treatment=treatment,
        outcome=outcome,
        graph=graph_dot,
    )
    identified_estimand = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(
        identified_estimand,
        method_name="backdoor.linear_regression",
        test_significance=False,
        confidence_intervals=True,
    )

    ci = None
    try:
        ci_raw = estimate.get_confidence_intervals()
        if ci_raw is not None:
            ci = [float(ci_raw[0][0]), float(ci_raw[0][1])]
    except Exception:
        ci = None

    refutations: dict[str, Any] = {}
    refuter_methods = {
        "placebo_treatment": "placebo_treatment_refuter",
        "random_common_cause": "random_common_cause",
        "data_subset": "data_subset_refuter",
    }
    for key, method_name in refuter_methods.items():
        try:
            refute = model.refute_estimate(
                identified_estimand,
                estimate,
                method_name=method_name,
            )
            refutations[key] = _refutation_to_payload(refute)
        except Exception as exc:
            refutations[key] = {"status": "error", "error": str(exc)}

    return EstimationResult(
        status="ok",
        method="DoWhy backdoor.linear_regression",
        estimand_text=str(identified_estimand),
        ate=float(estimate.value),
        confidence_intervals=ci,
        refutations=refutations,
        graph_dot=graph_dot,
    )


def _estimate_with_numpy(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
    graph_dot: str,
) -> EstimationResult:
    required_columns = [treatment, outcome, *confounders]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        return EstimationResult(
            status="error",
            method="降级线性调整估计",
            estimand_text="由于所选字段不存在，未能估计 ATE。",
            graph_dot=graph_dot,
            error=f"以下字段不存在：{', '.join(missing)}",
        )

    model_df = df[required_columns].dropna().copy()
    if model_df.empty:
        return EstimationResult(
            status="error",
            method="降级线性调整估计",
            estimand_text="由于没有完整样本行，未能估计 ATE。",
            graph_dot=graph_dot,
            error="删除缺失值后没有完整样本行。",
        )

    try:
        fit = _fit_adjusted_linear_effect(model_df, treatment, outcome, confounders)
        refutations = _fallback_refutations(model_df, treatment, outcome, confounders)
        return EstimationResult(
            status="ok",
            method="降级线性调整估计",
            estimand_text=(
                "使用 OLS 线性模型调整所选混杂变量，并将处理变量系数作为 ATE 的降级估计。"
                "若需要正式的因果识别和 refutation API，请安装 DoWhy。"
            ),
            ate=fit["ate"],
            confidence_intervals=fit["confidence_intervals"],
            refutations=refutations,
            graph_dot=graph_dot,
        )
    except Exception as exc:
        return EstimationResult(
            status="error",
            method="降级线性调整估计",
            estimand_text="ATE 估计失败。",
            graph_dot=graph_dot,
            error=str(exc),
        )


def _fit_adjusted_linear_effect(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
) -> dict[str, Any]:
    y = pd.to_numeric(df[outcome], errors="coerce")
    treatment_series = pd.to_numeric(df[treatment], errors="coerce")
    covariates = _encode_covariates(df, confounders)
    design = pd.concat(
        [
            pd.Series(1.0, index=df.index, name="intercept"),
            treatment_series.rename(treatment),
            covariates,
        ],
        axis=1,
    )
    valid = pd.concat([y, design], axis=1).dropna()
    if len(valid) < 3:
        raise ValueError("估计 ATE 至少需要 3 行完整数据。")

    y_values = valid[outcome].to_numpy(dtype=float)
    x_values = valid.drop(columns=[outcome]).to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(x_values, y_values, rcond=None)
    ate = float(coefficients[1])
    ci = _confidence_interval(x_values, y_values, coefficients, treatment_index=1)
    return {"ate": ate, "confidence_intervals": ci}


def _encode_covariates(df: pd.DataFrame, confounders: List[str]) -> pd.DataFrame:
    if not confounders:
        return pd.DataFrame(index=df.index)
    covariates = df[confounders].copy()
    return pd.get_dummies(covariates, drop_first=True, dtype=float)


def _confidence_interval(
    x_values: np.ndarray,
    y_values: np.ndarray,
    coefficients: np.ndarray,
    treatment_index: int,
) -> list[float] | None:
    residuals = y_values - x_values @ coefficients
    degrees_of_freedom = x_values.shape[0] - x_values.shape[1]
    if degrees_of_freedom <= 0:
        return None
    sigma_squared = float((residuals @ residuals) / degrees_of_freedom)
    covariance = sigma_squared * np.linalg.pinv(x_values.T @ x_values)
    standard_error = float(np.sqrt(max(covariance[treatment_index, treatment_index], 0.0)))
    estimate = float(coefficients[treatment_index])
    return [estimate - 1.96 * standard_error, estimate + 1.96 * standard_error]


def _fallback_refutations(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
) -> dict[str, Any]:
    rng = np.random.default_rng(123)
    baseline = _fit_adjusted_linear_effect(df, treatment, outcome, confounders)["ate"]

    placebo_df = df.copy()
    placebo_df[treatment] = rng.permutation(placebo_df[treatment].to_numpy())
    placebo = _fit_adjusted_linear_effect(placebo_df, treatment, outcome, confounders)["ate"]

    random_common_cause_df = df.copy()
    random_common_cause_df["_random_common_cause"] = rng.normal(size=len(df))
    random_common_cause = _fit_adjusted_linear_effect(
        random_common_cause_df,
        treatment,
        outcome,
        [*confounders, "_random_common_cause"],
    )["ate"]

    subset_df = df.sample(frac=0.8, random_state=123)
    subset = _fit_adjusted_linear_effect(subset_df, treatment, outcome, confounders)["ate"]

    return {
        "placebo_treatment": {
            "status": "ok",
            "estimated_effect": baseline,
            "new_effect": placebo,
            "absolute_difference_from_baseline": abs(placebo - baseline),
        },
        "random_common_cause": {
            "status": "ok",
            "estimated_effect": baseline,
            "new_effect": random_common_cause,
            "absolute_difference_from_baseline": abs(random_common_cause - baseline),
        },
        "data_subset": {
            "status": "ok",
            "estimated_effect": baseline,
            "new_effect": subset,
            "absolute_difference_from_baseline": abs(subset - baseline),
        },
    }


def _refutation_to_payload(refutation: Any) -> dict[str, Any]:
    result = getattr(refutation, "refutation_result", {}) or {}
    estimated_effect = _safe_float(getattr(refutation, "estimated_effect", None))
    new_effect = _safe_float(getattr(refutation, "new_effect", None))
    p_value = _safe_float(result.get("p_value")) if isinstance(result, dict) else None
    significant = result.get("is_statistically_significant") if isinstance(result, dict) else None

    text = str(refutation)
    if estimated_effect is None:
        estimated_effect = _parse_float_from_text(text, "Estimated effect")
    if new_effect is None:
        new_effect = _parse_float_from_text(text, "New effect")
    if p_value is None:
        p_value = _parse_float_from_text(text, "p value")

    payload: dict[str, Any] = {
        "status": "ok",
        "description": getattr(refutation, "refutation_type", None) or text.splitlines()[0],
        "estimated_effect": estimated_effect,
        "new_effect": new_effect,
        "p_value": p_value,
        "is_statistically_significant": _safe_bool(significant),
        "raw": text,
    }
    if estimated_effect is not None and new_effect is not None:
        payload["absolute_difference_from_baseline"] = abs(new_effect - estimated_effect)
    return payload


def _parse_float_from_text(text: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}\s*:\s*([-+0-9.eE]+)", text)
    if not match:
        return None
    return _safe_float(match.group(1))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        return bool(value)
    except (TypeError, ValueError):
        return None
