from __future__ import annotations

import json

from app.core.schemas import AgentResult, PipelineBundle
from app.services.deepseek_client import DeepSeekClient


class DeepSeekReporterAgent:
    name = "deepseek_reporter"

    def run(self, bundle: PipelineBundle) -> AgentResult:
        if not bundle.request.use_llm_report:
            return AgentResult(
                agent=self.name,
                status="skipped",
                payload={"reason": "未启用 DeepSeek 报告增强。"},
            )

        client = DeepSeekClient.from_env()
        if client is None:
            return AgentResult(
                agent=self.name,
                status="skipped",
                payload={"reason": "未配置 DEEPSEEK_API_KEY，已保留本地 Markdown 报告。"},
            )

        try:
            markdown = client.create_chat_completion(_build_messages(bundle))
        except Exception as exc:
            return AgentResult(
                agent=self.name,
                status="warning",
                payload={"reason": str(exc)},
                error=str(exc),
            )

        return AgentResult(
            agent=self.name,
            status="ok",
            payload={
                "markdown": markdown,
                "model": client.config.model,
                "base_url": client.config.base_url,
            },
        )


def _build_messages(bundle: PipelineBundle) -> list[dict[str, str]]:
    compact_payload = {
        "question": bundle.request.question,
        "variables": {
            "treatment": bundle.request.treatment,
            "outcome": bundle.request.outcome,
            "confounders": bundle.request.confounders,
            "effect_modifiers": bundle.request.effect_modifiers,
        },
        "profile": bundle.profile.model_dump() if bundle.profile else None,
        "method": bundle.method.model_dump() if bundle.method else None,
        "ate": bundle.estimate.model_dump() if bundle.estimate else None,
        "cate": bundle.cate.model_dump() if bundle.cate else None,
        "review": bundle.review.model_dump() if bundle.review else None,
        "base_report": bundle.report_markdown,
    }

    return [
        {
            "role": "system",
            "content": (
                "你是一名严谨的中文统计分析报告助手。请基于给定的结构化结果生成 Markdown 报告，"
                "不要编造未提供的数据，不要夸大因果结论，需要明确说明 ATE/CATE、稳健性检查和局限性。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请把下面的 multi-agent 因果分析结果改写成适合中文简历项目展示的 Markdown 报告。"
                "报告结构建议包括：分析问题、数据画像、变量配置、方法选择、ATE 结果、"
                "CATE 异质性结果、Reviewer 稳健性检查、局限性与下一步。\n\n"
                f"结构化结果 JSON：\n{json.dumps(compact_payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]
