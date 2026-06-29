from __future__ import annotations

from typing import Any

from app.core.schemas import PipelineBundle


def build_data_quality_markdown(data_quality: dict[str, Any] | None) -> str:
    if not data_quality:
        return ""

    summary = data_quality.get("summary", {})
    treatment_quality = data_quality.get("treatment_quality", {})
    outcome_quality = data_quality.get("outcome_quality", {})
    selected_quality = data_quality.get("selected_variables_quality", {})
    warnings = data_quality.get("warnings", [])
    recommendations = data_quality.get("recommendations", [])
    high_missingness_columns = summary.get("high_missingness_columns", [])
    selected_missingness = selected_quality.get("selected_missingness", {})

    lines = [
        "",
        "## Data Quality Summary",
        f"- Status: `{data_quality.get('status', 'unknown')}`",
        f"- Rows: {summary.get('row_count', 0)}",
        f"- Columns: {summary.get('column_count', 0)}",
        f"- Overall missing rate: {_format_rate(summary.get('overall_missing_rate'))}",
        f"- Duplicate rows: {summary.get('duplicate_rows_count', 0)} "
        f"({_format_rate(summary.get('duplicate_rate'))})",
        "",
        "### Missingness Overview",
        f"- High-missingness columns: {_join_or_none(high_missingness_columns)}",
        "",
    ]

    if selected_missingness:
        lines.append("- Selected variable missingness:")
        for column, payload in selected_missingness.items():
            lines.append(
                f"  - `{column}`: {payload.get('missing_count', 0)} missing "
                f"({_format_rate(payload.get('missing_rate'))})"
            )
    else:
        lines.append("- Selected variable missingness: None available")

    lines.extend(
        [
            "",
            "### Treatment Balance",
            f"- Treatment exists: {treatment_quality.get('exists', False)}",
            f"- Treatment has variation: {treatment_quality.get('has_variation')}",
            f"- Treatment missing rate: {_format_rate(treatment_quality.get('missing_rate'))}",
            f"- Treatment group counts: {_format_mapping(treatment_quality.get('group_counts', {}))}",
            "",
            "### Outcome Quality",
            f"- Outcome exists: {outcome_quality.get('exists', False)}",
            f"- Outcome has variation: {outcome_quality.get('has_variation')}",
            f"- Outcome missing rate: {_format_rate(outcome_quality.get('missing_rate'))}",
            "",
            "### Selected Variables Quality",
            f"- Selected variables: {_join_or_none(selected_quality.get('selected_variables', []))}",
            f"- Missing selected columns: {_join_or_none(selected_quality.get('missing_columns', []))}",
            f"- Complete-case rows: {selected_quality.get('selected_complete_case_count', 0)} "
            f"({_format_rate(selected_quality.get('selected_complete_case_rate'))})",
            "",
            "### Causal Readiness Warnings",
        ]
    )

    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- No major data quality warnings.")

    if recommendations:
        lines.extend(["", "### Data Quality Recommendations"])
        lines.extend(f"- {item}" for item in recommendations)

    lines.append("")
    return "\n".join(lines)


def build_interpretability_markdown(
    causal_trust: dict[str, Any] | None = None,
    sensitivity_summary: dict[str, Any] | None = None,
    heterogeneity_summary: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []

    if causal_trust:
        lines.extend(
            [
                "",
                "## Causal Trust Summary",
                f"- Status: `{causal_trust.get('status', 'unknown')}`",
                f"- Effect direction: `{causal_trust.get('effect_direction', 'unknown')}`",
                f"- Robustness level: `{causal_trust.get('robustness_level', 'unknown')}`",
                "",
                "### Key Warnings",
            ]
        )
        lines.extend(_markdown_list_or_message(causal_trust.get("key_warnings", []), "No key warnings available."))
        lines.extend(["", "### Recommendations"])
        lines.extend(
            _markdown_list_or_message(
                causal_trust.get("recommendations", []),
                "No recommendations available.",
            )
        )

    if sensitivity_summary:
        lines.extend(
            [
                "",
                "## Robustness / Sensitivity Notes",
                f"- Status: `{sensitivity_summary.get('status', 'unknown')}`",
                f"- Sensitivity status: `{sensitivity_summary.get('sensitivity_status', 'unknown')}`",
                "",
                "### Stability Notes",
            ]
        )
        lines.extend(
            _markdown_list_or_message(
                sensitivity_summary.get("stability_notes", []),
                "No sensitivity notes available.",
            )
        )
        warnings = sensitivity_summary.get("warnings", [])
        if warnings:
            lines.extend(["", "### Sensitivity Warnings"])
            lines.extend(_markdown_list_or_message(warnings, "No sensitivity warnings available."))
        limitations = sensitivity_summary.get("limitations", [])
        if limitations:
            lines.extend(["", "### Sensitivity Limitations"])
            lines.extend(_markdown_list_or_message(limitations, "No sensitivity limitations available."))

    if heterogeneity_summary:
        lines.extend(
            [
                "",
                "## Heterogeneity Explanation",
                f"- Status: `{heterogeneity_summary.get('status', 'unknown')}`",
                f"- CATE status: `{heterogeneity_summary.get('cate_status', 'unknown')}`",
                f"- Top effect modifiers: {_join_or_none(heterogeneity_summary.get('top_effect_modifiers', []))}",
                "",
                "### Business Interpretation",
                str(
                    heterogeneity_summary.get(
                        "business_interpretation",
                        "No heterogeneity explanation available.",
                    )
                ),
            ]
        )
        segment_summary = heterogeneity_summary.get("segment_effect_summary", {})
        if segment_summary:
            lines.extend(["", "### Segment Effect Summary"])
            for key, value in segment_summary.items():
                lines.append(f"- {key}: {value}")
        limitations = heterogeneity_summary.get("limitations", [])
        if limitations:
            lines.extend(["", "### Heterogeneity Limitations"])
            lines.extend(_markdown_list_or_message(limitations, "No heterogeneity limitations available."))

    if lines:
        lines.append("")
    return "\n".join(lines)


def build_markdown_report(bundle: PipelineBundle) -> str:
    request = bundle.request
    profile = bundle.profile
    method = bundle.method
    estimate = bundle.estimate
    cate = bundle.cate
    review = bundle.review

    lines = [
        "# Multi-Agent Causal Analytics Team Report",
        "",
        "## 分析问题",
        request.question,
        "",
        "## 变量配置",
        f"- 处理变量 Treatment：`{request.treatment}`",
        f"- 结果变量 Outcome：`{request.outcome}`",
        f"- 混杂变量 Confounders：{', '.join(request.confounders) or '未选择'}",
        f"- 效应修饰变量 Effect modifiers：{', '.join(request.effect_modifiers) or '未选择'}",
        "",
        "## Agent 执行计划",
        ", ".join(bundle.plan.get("steps", [])) or "未生成执行计划。",
        "",
    ]

    if profile:
        lines.extend(
            [
                "## 数据画像",
                f"- 样本行数：{profile.n_rows}",
                f"- 字段数量：{profile.n_cols}",
                f"- 数值字段：{', '.join(profile.numeric_columns) or '无'}",
                f"- 分类型字段：{', '.join(profile.categorical_columns) or '无'}",
                "",
            ]
        )

    if method:
        lines.extend(
            [
                "## 方法选择",
                f"- 首选方法：{method.primary}",
                f"- 备用方法：{method.secondary}",
                "- 主要假设：",
                *[f"  - {item}" for item in method.assumptions],
                "",
            ]
        )
        if method.warnings:
            lines.extend(["## 方法风险提示", *[f"- {item}" for item in method.warnings], ""])

    if estimate:
        lines.extend(
            [
                "## ATE 平均处理效应估计",
                f"- 状态：{estimate.status}",
                f"- 方法：{estimate.method}",
                f"- ATE：{estimate.ate:.6f}" if estimate.ate is not None else "- ATE：不可用",
                (
                    f"- 95% 置信区间：[{estimate.confidence_intervals[0]:.6f}, "
                    f"{estimate.confidence_intervals[1]:.6f}]"
                    if estimate.confidence_intervals
                    else "- 95% 置信区间：不可用"
                ),
                "",
                "## 稳健性检查",
            ]
        )
        if estimate.refutations:
            for name, result in estimate.refutations.items():
                if isinstance(result, dict):
                    new_effect = result.get("new_effect")
                    p_value = result.get("p_value")
                    diff = result.get("absolute_difference_from_baseline")
                    details = []
                    if new_effect is not None:
                        details.append(f"new_effect={float(new_effect):.6f}")
                    if diff is not None:
                        details.append(f"diff={float(diff):.6f}")
                    if p_value is not None:
                        details.append(f"p_value={float(p_value):.4f}")
                    lines.append(f"- {name}：{', '.join(details) or result.get('status', '可用')}")
                else:
                    lines.append(f"- {name}：`{result}`")
        else:
            lines.append("- 暂无 refutation 结果。")
        if estimate.warnings:
            lines.extend(["", "## 估计过程提示", *[f"- {item}" for item in estimate.warnings]])
        if estimate.error:
            lines.extend(["", "## 估计错误", estimate.error])
        lines.append("")

    if cate:
        lines.extend(
            [
                "## CATE 异质性分析",
                f"- 状态：{cate.status}",
                f"- 方法：{cate.method}",
                f"- CATE 均值：{cate.cate_mean:.6f}" if cate.cate_mean is not None else "- CATE 均值：不可用",
                f"- CATE 标准差：{cate.cate_std:.6f}" if cate.cate_std is not None else "- CATE 标准差：不可用",
                f"- 个体效应数量：{cate.n_effects}",
            ]
        )
        if cate.segment_summary:
            lines.append("- 分组摘要：")
            for key, value in cate.segment_summary.items():
                lines.append(f"  - {key}: {value}")
        if cate.warnings:
            lines.extend(["- 提示：", *[f"  - {item}" for item in cate.warnings]])
        if cate.error:
            lines.append(f"- 说明：{cate.error}")
        lines.append("")

    if review:
        lines.extend(
            [
                "## Reviewer 审阅摘要",
                f"- 状态：{review.status}",
                "- 检查项：",
                *[f"  - {key}: {value}" for key, value in review.checks.items()],
                "",
            ]
        )
        if review.warnings:
            lines.extend(["## Reviewer 风险提示", *[f"- {item}" for item in review.warnings], ""])

    lines.extend(
        [
            "## 说明",
            "EconML CATE 是可选功能；未安装 EconML 时会自动跳过。当前 MVP 不运行 LangGraph，也不依赖任何外部 LLM API；DeepSeek 报告增强是可选项，默认关闭。",
            "",
        ]
    )
    return "\n".join(lines)


def _format_rate(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "N/A"


def _join_or_none(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "None"


def _markdown_list_or_message(items: list[Any], message: str) -> list[str]:
    values = [item for item in items if item]
    if not values:
        return [f"- {message}"]
    return [f"- {item}" for item in values]


def _format_mapping(payload: dict[str, Any]) -> str:
    if not payload:
        return "None"
    return ", ".join(f"{key}: {value}" for key, value in payload.items())
