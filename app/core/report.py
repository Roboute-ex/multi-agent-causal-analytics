from __future__ import annotations

from app.core.schemas import PipelineBundle


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
