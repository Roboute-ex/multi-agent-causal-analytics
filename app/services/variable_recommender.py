from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from app.services.deepseek_client import DeepSeekClient


@dataclass
class VariableRecommendation:
    status: str
    treatment: str | None = None
    outcome: str | None = None
    confounders: list[str] = field(default_factory=list)
    effect_modifiers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def recommend_variables(
    question: str,
    columns: Iterable[str],
    profile: Mapping[str, Any] | None = None,
    client: Any | None = None,
) -> VariableRecommendation:
    columns_list = [str(column) for column in columns]
    if not columns_list:
        return VariableRecommendation(
            status="fallback",
            warnings=["当前数据集没有可用字段，无法推荐变量。"],
            reason="empty_columns",
        )

    if client is None:
        client = DeepSeekClient.from_env()
    if client is None:
        return VariableRecommendation(
            status="skipped",
            warnings=["未配置 DeepSeek API key，已跳过 LLM 变量推荐。"],
            reason="missing_api_key",
        )

    try:
        raw_response = client.create_chat_completion(
            _build_messages(question=question, columns=columns_list, profile=profile)
        )
    except Exception as exc:
        return VariableRecommendation(
            status="error",
            warnings=[f"LLM 变量推荐请求失败：{exc}"],
            reason="request_failed",
        )

    return parse_recommendation(raw_response, columns_list)


def parse_recommendation(raw_response: str, columns: Iterable[str]) -> VariableRecommendation:
    columns_list = [str(column) for column in columns]
    try:
        payload = json.loads(_extract_json_object(raw_response))
    except Exception as exc:
        return VariableRecommendation(
            status="fallback",
            warnings=[f"LLM 返回内容不是合法 JSON，已保留手动变量选择：{exc}"],
            reason="invalid_json",
        )

    if not isinstance(payload, dict):
        return VariableRecommendation(
            status="fallback",
            warnings=["LLM 返回 JSON 不是对象，已保留手动变量选择。"],
            reason="invalid_json_shape",
        )

    recommendation = VariableRecommendation(
        status="ok",
        treatment=_string_or_none(payload.get("treatment")),
        outcome=_string_or_none(payload.get("outcome")),
        confounders=_list_of_strings(payload.get("confounders")),
        effect_modifiers=_list_of_strings(payload.get("effect_modifiers")),
        reason=_string_or_none(payload.get("reason")) or "llm_recommendation",
    )
    return validate_recommendation(recommendation, columns_list)


def validate_recommendation(
    recommendation: VariableRecommendation,
    columns: Iterable[str],
) -> VariableRecommendation:
    valid_columns = set(columns)
    warnings = list(recommendation.warnings)

    treatment = recommendation.treatment
    if treatment not in valid_columns:
        if treatment:
            warnings.append(f"推荐的 treatment 字段不存在，已忽略：{treatment}")
        else:
            warnings.append("LLM 未返回有效 treatment。")
        treatment = None

    outcome = recommendation.outcome
    if outcome not in valid_columns:
        if outcome:
            warnings.append(f"推荐的 outcome 字段不存在，已忽略：{outcome}")
        else:
            warnings.append("LLM 未返回有效 outcome。")
        outcome = None

    blocked = {value for value in [treatment, outcome] if value}
    confounders, confounder_warnings = _clean_column_list(
        values=recommendation.confounders,
        valid_columns=valid_columns,
        blocked_columns=blocked,
        field_name="confounders",
    )
    effect_modifiers, modifier_warnings = _clean_column_list(
        values=recommendation.effect_modifiers,
        valid_columns=valid_columns,
        blocked_columns=blocked,
        field_name="effect_modifiers",
    )
    warnings.extend(confounder_warnings)
    warnings.extend(modifier_warnings)

    return VariableRecommendation(
        status=recommendation.status,
        treatment=treatment,
        outcome=outcome,
        confounders=confounders,
        effect_modifiers=effect_modifiers,
        warnings=warnings,
        reason=recommendation.reason,
    )


def _build_messages(
    question: str,
    columns: list[str],
    profile: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    profile_payload = profile or {}
    return [
        {
            "role": "system",
            "content": (
                "你是严谨的因果分析变量推荐助手。只根据用户问题、字段名和简单字段画像推荐变量，"
                "不要编造不存在的字段，不要声称已经证明因果关系。必须只返回 JSON 对象。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请为因果分析推荐变量。返回 JSON，固定字段为 treatment、outcome、"
                "confounders、effect_modifiers、reason。treatment/outcome 使用字符串或 null，"
                "confounders/effect_modifiers 使用字符串数组。只能使用 columns 中存在的字段。\n\n"
                f"用户问题：{question}\n"
                f"columns：{json.dumps(columns, ensure_ascii=False)}\n"
                f"profile：{json.dumps(profile_payload, ensure_ascii=False, default=str)}"
            ),
        },
    ]


def _extract_json_object(raw_response: str) -> str:
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("未找到 JSON 对象。")
    return text[start : end + 1]


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _clean_column_list(
    values: list[str],
    valid_columns: set[str],
    blocked_columns: set[str],
    field_name: str,
) -> tuple[list[str], list[str]]:
    cleaned = []
    seen = set()
    warnings = []

    for value in values:
        if value not in valid_columns:
            warnings.append(f"推荐的 {field_name} 字段不存在，已忽略：{value}")
            continue
        if value in blocked_columns:
            warnings.append(f"{field_name} 不能包含 treatment/outcome，已移除：{value}")
            continue
        if value in seen:
            warnings.append(f"推荐的 {field_name} 字段重复，已去重：{value}")
            continue
        seen.add(value)
        cleaned.append(value)

    return cleaned, warnings
