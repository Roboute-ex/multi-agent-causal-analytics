from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.orchestrator import AnalyticsTeamOrchestrator
from app.core.schemas import AnalysisRequest
from app.services.data_loader import is_excel_file, list_excel_sheets, read_dataset


DEFAULT_DATASET = Path("data/sample_marketing.csv")
AGENT_FLOW = "Data Engineer → Statistician → Causal Agent → Heterogeneity Agent → Reviewer → Reporter"


def _default_index(columns: list[str], column_name: str) -> int:
    return columns.index(column_name) if column_name in columns else 0


def _default_confounders(columns: list[str]) -> list[str]:
    preferred = ["age", "income", "prior_spend", "visits"]
    return [column for column in preferred if column in columns]


def _refutations_to_table(refutations: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name, payload in refutations.items():
        if isinstance(payload, dict):
            rows.append(
                {
                    "refutation": name,
                    "status": payload.get("status", "unknown"),
                    "estimated_effect": payload.get("estimated_effect"),
                    "new_effect": payload.get("new_effect"),
                    "difference": payload.get("absolute_difference_from_baseline"),
                    "p_value": payload.get("p_value"),
                    "error": payload.get("error"),
                }
            )
        else:
            rows.append(
                {
                    "refutation": name,
                    "status": "available",
                    "estimated_effect": None,
                    "new_effect": None,
                    "difference": None,
                    "p_value": None,
                    "error": str(payload),
                }
            )
    return pd.DataFrame(rows)


def _show_cate_status(status: str) -> None:
    label = f"CATE 状态：{status}"
    if status == "ok":
        st.success(label)
    elif status == "skipped":
        st.info(label)
    elif status == "error":
        st.error(label)
    else:
        st.warning(label)


st.set_page_config(page_title="Multi-Agent Causal Analytics Team", layout="wide")
st.title("Multi-Agent Causal Analytics Team")
st.caption("一个用于因果分析的多 Agent 数据分析团队")
st.markdown(f"**Agent 流程：** `{AGENT_FLOW}`")
st.divider()

source = st.radio("数据来源", ["使用样例数据", "上传文件"], horizontal=True)
df: pd.DataFrame | None = None
dataset_path = str(DEFAULT_DATASET)

if source == "使用样例数据":
    if DEFAULT_DATASET.exists():
        df = read_dataset(DEFAULT_DATASET)
    else:
        st.warning("未找到样例数据。请先运行 `python data/generate_synthetic.py`。")
else:
    uploaded = st.file_uploader("上传 CSV 或 Excel 文件", type=["csv", "xlsx", "xls", "xlsm"])
    if uploaded is not None:
        dataset_path = uploaded.name
        try:
            if is_excel_file(uploaded.name):
                sheets = list_excel_sheets(uploaded)
                uploaded.seek(0)
                sheet_name = st.selectbox("选择 Excel 工作表", sheets)
                df = read_dataset(uploaded, sheet_name=sheet_name)
            else:
                df = read_dataset(uploaded)
        except Exception as exc:
            st.error(f"读取文件失败：{exc}")
            df = None

if df is not None:
    columns = df.columns.tolist()
    st.dataframe(df.head(20), use_container_width=True)

    question = st.text_input(
        "分析问题",
        value="优惠券是否提升购买概率？",
    )
    treatment = st.selectbox(
        "处理变量 Treatment",
        columns,
        index=_default_index(columns, "coupon"),
    )
    outcome = st.selectbox(
        "结果变量 Outcome",
        columns,
        index=_default_index(columns, "purchase"),
    )
    confounders = st.multiselect(
        "混杂变量 Confounders",
        columns,
        default=_default_confounders(columns),
    )
    effect_modifiers = st.multiselect(
        "效应修饰变量 Effect modifiers",
        columns,
        default=["visits"] if "visits" in columns else [],
    )
    use_llm_report = st.checkbox(
        "可选：启用 DeepSeek 报告增强（不属于 MVP 验收条件）",
        value=False,
        help="默认关闭。需要在 .env 中配置 DEEPSEEK_API_KEY；未配置或调用失败时会自动保留本地 Markdown 报告。",
    )

    if st.button("运行 Multi-Agent 因果分析", type="primary"):
        request = AnalysisRequest(
            question=question,
            dataset_path=dataset_path,
            treatment=treatment,
            outcome=outcome,
            confounders=confounders,
            effect_modifiers=effect_modifiers,
            use_llm_report=use_llm_report,
        )
        bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)

        if bundle.estimate and bundle.estimate.ate is not None:
            metric_cols = st.columns(3)
            metric_cols[0].metric("ATE", f"{bundle.estimate.ate:.4f}")
            metric_cols[1].metric("估计方法", bundle.estimate.method)
            metric_cols[2].metric("Reviewer 状态", bundle.review.status if bundle.review else "未知")

            if bundle.estimate.confidence_intervals:
                st.caption(
                    "95% 置信区间："
                    f"[{bundle.estimate.confidence_intervals[0]:.4f}, "
                    f"{bundle.estimate.confidence_intervals[1]:.4f}]"
                )
        elif bundle.estimate and bundle.estimate.error:
            st.error(bundle.estimate.error)

        if bundle.cate:
            _show_cate_status(bundle.cate.status)
            if bundle.cate.status == "ok" and bundle.cate.cate_mean is not None:
                cate_cols = st.columns(2)
                cate_cols[0].metric("CATE 均值", f"{bundle.cate.cate_mean:.4f}")
                cate_cols[1].metric("CATE 标准差", f"{bundle.cate.cate_std or 0.0:.4f}")
            elif bundle.cate.status == "skipped":
                st.info(bundle.cate.error or "CATE 分析已跳过。")
            elif bundle.cate.status == "error":
                st.warning(bundle.cate.error or "CATE 分析失败，但主流程已继续。")

        tab_report, tab_robustness, tab_cate, tab_agents = st.tabs(
            ["分析报告", "稳健性检查", "CATE 异质性", "Agent 日志"]
        )

        with tab_report:
            st.markdown(bundle.report_markdown or "")
            st.download_button(
                "下载 Markdown 报告",
                data=bundle.report_markdown or "",
                file_name="multi_agent_causal_report.md",
                mime="text/markdown",
            )

        with tab_robustness:
            if bundle.estimate:
                if bundle.estimate.graph_dot:
                    with st.expander("因果 DAG", expanded=False):
                        st.graphviz_chart(bundle.estimate.graph_dot)
                        st.code(bundle.estimate.graph_dot, language="dot")
                st.subheader("Refutation 结果")
                refutation_table = _refutations_to_table(bundle.estimate.refutations)
                if refutation_table.empty:
                    st.info("暂无 refutation 结果。")
                else:
                    st.dataframe(refutation_table, use_container_width=True, hide_index=True)
                    with st.expander("查看原始 refutation payload", expanded=False):
                        st.json(bundle.estimate.refutations)
            if bundle.review:
                st.subheader("Reviewer 检查")
                if bundle.review.warnings:
                    for warning in bundle.review.warnings:
                        st.warning(warning)
                else:
                    st.success("Reviewer 未发现额外风险提示。")
                st.json(bundle.review.model_dump())

        with tab_cate:
            if bundle.cate:
                st.json(bundle.cate.model_dump())

        with tab_agents:
            for result in bundle.agent_logs:
                with st.expander(f"{result.agent}: {result.status}", expanded=False):
                    st.json(result.payload)
