from __future__ import annotations

import warnings
from typing import List

import numpy as np
import pandas as pd

from app.core.schemas import CateResult

MIN_CATE_ROWS = 200


def estimate_cate(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: List[str],
    effect_modifiers: List[str],
) -> CateResult:
    if not effect_modifiers:
        return CateResult(
            status="skipped",
            error="未选择 effect_modifiers，已跳过 CATE 异质性分析。",
        )

    missing = [
        column
        for column in [treatment, outcome, *confounders, *effect_modifiers]
        if column not in df.columns
    ]
    if missing:
        return CateResult(
            status="error",
            error=f"CATE 分析所需字段不存在：{', '.join(sorted(set(missing)))}",
        )

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*set_(bad|over|under) function will be deprecated.*",
                category=PendingDeprecationWarning,
            )
            from econml.dml import LinearDML
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    except ImportError as exc:
        return CateResult(
            status="skipped",
            error=f"未安装 EconML，已跳过 CATE 异质性分析：{exc}",
        )

    try:
        selected_columns = _unique_columns([treatment, outcome, *confounders, *effect_modifiers])
        model_df = df[selected_columns].dropna().copy()
        if len(model_df) < MIN_CATE_ROWS:
            return CateResult(
                status="error",
                error=f"EconML CATE 分析至少需要 {MIN_CATE_ROWS} 行完整数据。",
            )

        y = pd.to_numeric(model_df[outcome], errors="coerce")
        t = pd.to_numeric(model_df[treatment], errors="coerce")
        x = pd.get_dummies(model_df[effect_modifiers], drop_first=True, dtype=float).add_prefix("x__")
        w_columns = [column for column in confounders if column not in effect_modifiers]
        w = (
            pd.get_dummies(model_df[w_columns], drop_first=True, dtype=float).add_prefix("w__")
            if w_columns
            else None
        )

        analysis_df = pd.concat([y.rename(outcome), t.rename(treatment), x], axis=1)
        if w is not None:
            analysis_df = pd.concat([analysis_df, w], axis=1)
        analysis_df = analysis_df.dropna()
        if len(analysis_df) < MIN_CATE_ROWS:
            return CateResult(
                status="error",
                error=f"EconML CATE 分析至少需要 {MIN_CATE_ROWS} 行数值型完整数据。",
            )

        y_values = analysis_df[outcome].to_numpy(dtype=float)
        t_values = analysis_df[treatment].to_numpy(dtype=float)
        x_values = analysis_df[x.columns].to_numpy(dtype=float)
        w_values = analysis_df[w.columns].to_numpy(dtype=float) if w is not None else None

        treatment_values = set(np.unique(t_values).tolist())
        is_binary_treatment = treatment_values.issubset({0.0, 1.0})
        model_t = (
            RandomForestClassifier(
                n_estimators=80,
                min_samples_leaf=20,
                max_depth=6,
                random_state=42,
                n_jobs=1,
            )
            if is_binary_treatment
            else RandomForestRegressor(
                n_estimators=80,
                min_samples_leaf=20,
                max_depth=6,
                random_state=42,
                n_jobs=1,
            )
        )

        estimator = LinearDML(
            model_y=RandomForestRegressor(
                n_estimators=80,
                min_samples_leaf=20,
                max_depth=6,
                random_state=42,
                n_jobs=1,
            ),
            model_t=model_t,
            discrete_treatment=is_binary_treatment,
            cv=3,
            mc_iters=2,
            mc_agg="mean",
            random_state=42,
        )
        estimator.fit(Y=y_values, T=t_values, X=x_values, W=w_values, inference=None)
        cate_values = np.asarray(estimator.effect(X=x_values), dtype=float).reshape(-1)

        segment_summary = _segment_summary(
            source=model_df.loc[analysis_df.index],
            first_modifier=effect_modifiers[0],
            cate_values=cate_values,
        )
        return CateResult(
            status="ok",
            method="EconML LinearDML",
            cate_mean=float(np.mean(cate_values)),
            cate_std=float(np.std(cate_values)),
            n_effects=int(len(cate_values)),
            segment_summary=segment_summary,
        )
    except Exception as exc:
        return CateResult(status="error", method="EconML LinearDML", error=str(exc))


def _segment_summary(
    source: pd.DataFrame,
    first_modifier: str,
    cate_values: np.ndarray,
) -> dict[str, float | int | str]:
    modifier = source[first_modifier]
    if pd.api.types.is_numeric_dtype(modifier):
        threshold = float(modifier.median())
        low_mask = modifier <= threshold
        high_mask = modifier > threshold
        return {
            "modifier": first_modifier,
            "threshold": threshold,
            "low_group_mean": float(np.mean(cate_values[low_mask.to_numpy()])),
            "high_group_mean": float(np.mean(cate_values[high_mask.to_numpy()])),
            "low_group_n": int(np.sum(low_mask)),
            "high_group_n": int(np.sum(high_mask)),
        }

    temp = pd.DataFrame(
        {
            first_modifier: modifier.astype(str).to_numpy(),
            "_cate": cate_values,
        }
    )
    grouped = temp.groupby(first_modifier)["_cate"].mean().sort_values(ascending=False)
    return {
        "modifier": first_modifier,
        **{str(key): float(value) for key, value in grouped.head(10).items()},
    }


def _unique_columns(columns: list[str]) -> list[str]:
    return list(dict.fromkeys(columns))
