from __future__ import annotations

from typing import Dict

import pandas as pd

from app.core.report import build_markdown_report
from app.core.schemas import (
    AgentResult,
    AnalysisRequest,
    PipelineBundle,
    ReviewResult,
)
from app.services.causal_dowhy import estimate_ate
from app.services.cate_econml import estimate_cate
from app.services.method_service import choose_method, missing_columns, selected_columns
from app.services.profile_service import build_profile


REQUIRED_REFUTATIONS = ("placebo_treatment", "random_common_cause", "data_subset")


class CoordinatorAgent:
    name = "coordinator"

    def run(self, request: AnalysisRequest) -> AgentResult:
        return AgentResult(
            agent=self.name,
            status="ok",
            payload={
                "route": "causal_analytics_mvp",
                "steps": [
                    "数据画像",
                    "方法选择",
                    "ATE 因果效应估计",
                    "可选 CATE 异质性分析",
                    "Reviewer 稳健性审查",
                    "生成 Markdown 报告",
                ],
                "question": request.question,
            },
        )


class DataEngineerAgent:
    name = "data_engineer"

    def run(self, df: pd.DataFrame) -> AgentResult:
        profile = build_profile(df)
        return AgentResult(agent=self.name, status="ok", payload=profile.model_dump())


class StatisticianAgent:
    name = "statistician"

    def run(self, request: AnalysisRequest, profile) -> AgentResult:
        recommendation = choose_method(request, profile)
        return AgentResult(
            agent=self.name,
            status="ok" if not recommendation.warnings else "warning",
            payload=recommendation.model_dump(),
        )


class CausalAgent:
    name = "causal"

    def run(self, df: pd.DataFrame, request: AnalysisRequest) -> AgentResult:
        estimate = estimate_ate(
            df=df,
            treatment=request.treatment,
            outcome=request.outcome,
            confounders=request.confounders,
            effect_modifiers=request.effect_modifiers,
        )
        return AgentResult(
            agent=self.name,
            status=estimate.status,
            payload=estimate.model_dump(),
            error=estimate.error,
        )


class HeterogeneityAgent:
    name = "heterogeneity"

    def run(self, df: pd.DataFrame, request: AnalysisRequest) -> AgentResult:
        cate = estimate_cate(
            df=df,
            treatment=request.treatment,
            outcome=request.outcome,
            confounders=request.confounders,
            effect_modifiers=request.effect_modifiers,
        )
        return AgentResult(
            agent=self.name,
            status=cate.status,
            payload=cate.model_dump(),
            error=cate.error,
        )


class ReviewerAgent:
    name = "reviewer"

    def run(self, bundle: PipelineBundle) -> AgentResult:
        profile = bundle.profile
        request = bundle.request
        method_warnings = bundle.method.warnings if bundle.method else []

        selected_missing = []
        if profile:
            selected_missing = missing_columns(profile.dtypes.keys(), selected_columns(request))
        refutations = bundle.estimate.refutations if bundle.estimate else {}
        missing_refutations = [
            refutation for refutation in REQUIRED_REFUTATIONS if refutation not in refutations
        ]

        checks: Dict[str, object] = {
            "has_profile": profile is not None,
            "has_rows": bool(profile and profile.n_rows > 0),
            "selected_columns_present": not selected_missing,
            "has_treatment": bool(request.treatment),
            "has_outcome": bool(request.outcome),
            "has_ate_estimate": bool(bundle.estimate and bundle.estimate.ate is not None),
            "has_refutations": bool(bundle.estimate and bundle.estimate.refutations),
            "has_required_refutations": not missing_refutations,
            "cate_optional_handled": bool(
                bundle.cate and bundle.cate.status in {"ok", "skipped", "error"}
            ),
        }
        warnings = list(method_warnings)
        if selected_missing:
            warnings.append(f"无法分析不存在的字段：{', '.join(selected_missing)}")
        if missing_refutations:
            warnings.append(f"缺少必要的 refutation 结果：{', '.join(missing_refutations)}")
        if bundle.estimate and bundle.estimate.warnings:
            warnings.extend(bundle.estimate.warnings)
        if bundle.estimate and bundle.estimate.status == "error" and bundle.estimate.error:
            warnings.append(bundle.estimate.error)
        if bundle.cate and bundle.cate.status == "error" and bundle.cate.error:
            warnings.append(bundle.cate.error)
        if bundle.estimate and bundle.estimate.ate is not None:
            robustness_checks, robustness_warnings = _review_refutations(
                bundle.estimate.ate,
                bundle.estimate.refutations,
            )
            checks.update(robustness_checks)
            warnings.extend(robustness_warnings)

        status = "ok" if all(checks.values()) and not warnings else "warning"
        review = ReviewResult(status=status, checks=checks, warnings=warnings)
        return AgentResult(agent=self.name, status=status, payload=review.model_dump())


class ReporterAgent:
    name = "reporter"

    def run(self, bundle: PipelineBundle) -> AgentResult:
        markdown = build_markdown_report(bundle)
        return AgentResult(agent=self.name, status="ok", payload={"markdown": markdown})


def _review_refutations(
    ate: float,
    refutations: Dict[str, object],
) -> tuple[Dict[str, bool], list[str]]:
    tolerance = max(0.05, abs(ate) * 0.50)
    checks: Dict[str, bool] = {}
    warnings: list[str] = []

    placebo = _refutation_effect(refutations.get("placebo_treatment"))
    if placebo is not None:
        checks["placebo_near_zero"] = abs(placebo) <= tolerance
        if not checks["placebo_near_zero"]:
            warnings.append("Placebo treatment refuter 的新效应没有接近 0。")

    random_common_cause = _refutation_effect(refutations.get("random_common_cause"))
    if random_common_cause is not None:
        checks["random_common_cause_stable"] = abs(random_common_cause - ate) <= tolerance
        if not checks["random_common_cause_stable"]:
            warnings.append("Random common cause refuter 使估计结果发生了明显变化。")

    subset = _refutation_effect(refutations.get("data_subset"))
    if subset is not None:
        checks["data_subset_stable"] = abs(subset - ate) <= tolerance
        if not checks["data_subset_stable"]:
            warnings.append("Data subset refuter 使估计结果发生了明显变化。")

    return checks, warnings


def _refutation_effect(payload: object) -> float | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("new_effect")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
