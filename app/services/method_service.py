from __future__ import annotations

from typing import Iterable, List

from app.core.schemas import AnalysisRequest, DataProfile, MethodRecommendation


def selected_columns(request: AnalysisRequest) -> List[str]:
    return [
        request.treatment,
        request.outcome,
        *request.confounders,
        *request.effect_modifiers,
    ]


def missing_columns(columns: Iterable[str], expected: Iterable[str]) -> List[str]:
    available = set(columns)
    return sorted({column for column in expected if column not in available})


def choose_method(request: AnalysisRequest, profile: DataProfile) -> MethodRecommendation:
    missing = missing_columns(profile.dtypes.keys(), selected_columns(request))
    high_missing = [
        column for column, rate in profile.missing_rate.items() if rate > 0.20
    ]

    warnings = []
    if missing:
        warnings.append(f"以下已选择字段不存在：{', '.join(missing)}")
    if high_missing:
        warnings.append(f"以下字段缺失率超过 20%：{', '.join(high_missing)}")
    if request.treatment not in profile.numeric_columns:
        warnings.append("处理变量不是数值型；进行因果估计前建议先编码。")
    if request.outcome not in profile.numeric_columns:
        warnings.append("结果变量不是数值型；当前 MVP 建议选择数值型结果变量。")

    return MethodRecommendation(
        primary="DoWhy backdoor.linear_regression（可用时优先）",
        secondary="降级线性调整估计",
        assumptions=[
            "已明确选择处理变量和结果变量。",
            "混杂变量由分析者根据业务与统计知识指定。",
            "降级估计器会用线性模型调整所选混杂变量。",
            "若需要正式的因果识别和 refutation API，建议安装 DoWhy。",
        ],
        warnings=warnings,
    )
