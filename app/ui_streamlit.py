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
from app.core.pdf_export import PDFExportUnavailableError, build_pdf_report, is_pdf_export_available
from app.core.report import build_data_quality_markdown
from app.core.report_export import build_html_report
from app.core.schemas import AnalysisRequest
from app.graph.langgraph_runner import (
    LangGraphUnavailableError,
    is_langgraph_available,
    run_langgraph_pipeline,
)
from app.services.data_loader import is_excel_file, list_excel_sheets, read_dataset
from app.services.data_quality import run_data_quality_checks
from app.services.variable_recommender import VariableRecommendation, recommend_variables


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


def _build_variable_profile(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "n_rows": int(len(df)),
        "columns": [
            {
                "name": column,
                "dtype": str(dtype),
                "missing_rate": float(df[column].isna().mean()),
            }
            for column, dtype in df.dtypes.items()
        ],
    }


def _apply_recommendation(recommendation: VariableRecommendation) -> None:
    if recommendation.treatment:
        st.session_state["selected_treatment"] = recommendation.treatment
    if recommendation.outcome:
        st.session_state["selected_outcome"] = recommendation.outcome
    st.session_state["selected_confounders"] = recommendation.confounders
    st.session_state["selected_effect_modifiers"] = recommendation.effect_modifiers


def _selector_index(columns: list[str], session_key: str, fallback: str) -> int:
    value = st.session_state.get(session_key, fallback)
    if value in columns:
        return columns.index(value)
    return _default_index(columns, fallback)


def _show_data_quality_summary(
    data_quality: dict[str, Any],
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
) -> None:
    summary = data_quality.get("summary", {})
    selected_quality = data_quality.get("selected_variables_quality", {})
    warnings = data_quality.get("warnings", [])

    with st.expander("Data Quality Summary", expanded=True):
        status = data_quality.get("status", "unknown")
        status_label = f"Data quality status: {status}"
        if status == "ok":
            st.success(status_label)
        elif status == "warning":
            st.warning(status_label)
        else:
            st.error(status_label)

        metric_cols = st.columns(5)
        metric_cols[0].metric("Rows", summary.get("row_count", 0))
        metric_cols[1].metric("Columns", summary.get("column_count", 0))
        metric_cols[2].metric("Duplicate rows", summary.get("duplicate_rows_count", 0))
        metric_cols[3].metric("Warnings", len(warnings))
        metric_cols[4].metric(
            "Complete cases",
            selected_quality.get("selected_complete_case_count", 0),
        )

        chart_cols = st.columns(2)
        missing_rate_frame = _missing_rate_frame(data_quality)
        with chart_cols[0]:
            st.markdown("**Missing rate by column**")
            if missing_rate_frame.empty:
                st.info("No column missingness data available.")
            else:
                st.bar_chart(missing_rate_frame.set_index("column")["missing_rate"])

        selected_missingness_frame = _selected_missingness_frame(data_quality)
        with chart_cols[1]:
            st.markdown("**Selected variables missingness**")
            if selected_missingness_frame.empty:
                st.info("No selected variable missingness data available.")
            else:
                st.bar_chart(selected_missingness_frame.set_index("column")["missing_rate"])

        treatment_cols = st.columns(2)
        treatment_counts_frame = _treatment_counts_frame(data_quality)
        with treatment_cols[0]:
            st.markdown("**Treatment group counts**")
            if treatment_counts_frame.empty:
                st.info("No treatment group count data available.")
            else:
                st.bar_chart(treatment_counts_frame.set_index("group")["count"])

        outcome_frame = _outcome_by_treatment_frame(df, treatment, outcome)
        with treatment_cols[1]:
            st.markdown("**Outcome by treatment mean**")
            if outcome_frame.empty:
                outcome_quality = data_quality.get("outcome_quality", {})
                st.json(outcome_quality)
            else:
                st.bar_chart(outcome_frame.set_index("treatment")["mean_outcome"])

        if warnings:
            st.markdown("**Data quality warnings**")
            st.dataframe(pd.DataFrame({"warning": warnings}), use_container_width=True, hide_index=True)
        else:
            st.success("No major data quality warnings.")


def _missing_rate_frame(data_quality: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "column": str(item.get("column", "")),
            "missing_rate": float(item.get("missing_rate") or 0.0),
        }
        for item in data_quality.get("column_quality", [])
    ]
    return pd.DataFrame(rows)


def _selected_missingness_frame(data_quality: dict[str, Any]) -> pd.DataFrame:
    selected_quality = data_quality.get("selected_variables_quality", {})
    selected_missingness = selected_quality.get("selected_missingness", {})
    rows = [
        {
            "column": str(column),
            "missing_rate": float(payload.get("missing_rate") or 0.0),
        }
        for column, payload in selected_missingness.items()
        if isinstance(payload, dict)
    ]
    return pd.DataFrame(rows)


def _treatment_counts_frame(data_quality: dict[str, Any]) -> pd.DataFrame:
    treatment_quality = data_quality.get("treatment_quality", {})
    group_counts = treatment_quality.get("group_counts", {})
    rows = [{"group": str(group), "count": int(count)} for group, count in group_counts.items()]
    return pd.DataFrame(rows)


def _outcome_by_treatment_frame(df: pd.DataFrame, treatment: str, outcome: str) -> pd.DataFrame:
    if treatment not in df.columns or outcome not in df.columns:
        return pd.DataFrame()
    frame = pd.DataFrame(
        {
            "treatment": df[treatment].astype(str),
            "outcome": pd.to_numeric(df[outcome], errors="coerce"),
        }
    ).dropna(subset=["outcome"])
    if frame.empty:
        return pd.DataFrame()
    return frame.groupby("treatment", dropna=False)["outcome"].mean().reset_index(name="mean_outcome")


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
    if not columns:
        data_quality = run_data_quality_checks(df)
        _show_data_quality_summary(data_quality, df, "", "")
        st.stop()

    question = st.text_input(
        "自然语言分析问题",
        value="优惠券是否提升购买概率？",
        key="analysis_question",
    )

    with st.expander("LLM-assisted Variable Recommendation", expanded=False):
        st.caption(
            "可选功能，默认关闭。只有点击推荐按钮时才会调用 DeepSeek；没有 API key 或推荐失败时，手动变量选择仍然可用。"
        )
        if st.button("Recommend variables with LLM"):
            recommendation = recommend_variables(
                question=question,
                columns=columns,
                profile=_build_variable_profile(df),
            )
            st.session_state["variable_recommendation"] = recommendation.to_dict()

        recommendation_payload = st.session_state.get("variable_recommendation")
        if recommendation_payload:
            recommendation = VariableRecommendation(**recommendation_payload)
            st.json(recommendation.to_dict())
            if recommendation.warnings:
                for warning in recommendation.warnings:
                    st.warning(warning)
            if recommendation.status == "ok":
                st.success("LLM 已生成变量推荐。你可以应用推荐，也可以继续手动选择。")
            elif recommendation.status == "skipped":
                st.info("LLM 变量推荐已跳过。你仍然可以手动选择变量。")
            elif recommendation.status == "fallback":
                st.warning("LLM 返回格式不可用，已保留手动变量选择。")
            else:
                st.error("LLM 变量推荐失败，已保留手动变量选择。")

            if st.button("Apply recommendation to current selectors"):
                _apply_recommendation(recommendation)
                st.success("已将可用推荐应用到当前变量选择。你仍然可以继续手动修改。")

    treatment = st.selectbox(
        "处理变量 Treatment",
        columns,
        index=_selector_index(columns, "selected_treatment", "coupon"),
        key="selected_treatment",
    )
    outcome = st.selectbox(
        "结果变量 Outcome",
        columns,
        index=_selector_index(columns, "selected_outcome", "purchase"),
        key="selected_outcome",
    )
    confounders = st.multiselect(
        "混杂变量 Confounders",
        columns,
        default=_default_confounders(columns),
        key="selected_confounders",
    )
    effect_modifiers = st.multiselect(
        "效应修饰变量 Effect modifiers",
        columns,
        default=["visits"] if "visits" in columns else [],
        key="selected_effect_modifiers",
    )
    data_quality = run_data_quality_checks(
        df,
        treatment=treatment,
        outcome=outcome,
        confounders=confounders,
        effect_modifiers=effect_modifiers,
    )
    _show_data_quality_summary(data_quality, df, treatment, outcome)

    use_llm_report = st.checkbox(
        "可选：启用 DeepSeek 报告增强（不属于 MVP 验收条件）",
        value=False,
        help="默认关闭。需要在 .env 中配置 DEEPSEEK_API_KEY；未配置或调用失败时会自动保留本地 Markdown 报告。",
    )
    use_langgraph = st.checkbox(
        "Use experimental LangGraph orchestration",
        value=False,
        help="默认关闭。仅在已安装 requirements-langgraph.txt 时使用 LangGraph 编排现有 Agent；未安装时会自动回退到 deterministic orchestrator。",
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
        orchestration_mode = "deterministic"
        if use_langgraph:
            if is_langgraph_available():
                try:
                    bundle = run_langgraph_pipeline(request, df)
                    orchestration_mode = "langgraph_experimental"
                except LangGraphUnavailableError as exc:
                    st.warning(f"LangGraph orchestration unavailable：{exc} 已回退到 deterministic orchestrator。")
                    bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)
                    orchestration_mode = "deterministic_fallback_langgraph_unavailable"
            else:
                st.warning(
                    "LangGraph 未安装，已回退到 deterministic orchestrator。"
                    "如需启用，请安装 requirements-langgraph.txt。"
                )
                bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)
                orchestration_mode = "deterministic_fallback_langgraph_unavailable"
        else:
            bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)

        st.caption(f"Orchestration mode: `{orchestration_mode}`")

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
            report_markdown = bundle.report_markdown or ""
            data_quality_markdown = build_data_quality_markdown(data_quality)
            if data_quality_markdown:
                report_markdown = (
                    f"{report_markdown}\n{data_quality_markdown}"
                    if report_markdown
                    else data_quality_markdown
                )
            st.markdown(report_markdown)
            download_cols = st.columns(3)
            with download_cols[0]:
                st.download_button(
                    "下载 Markdown 报告",
                    data=report_markdown,
                    file_name="multi_agent_causal_report.md",
                    mime="text/markdown",
                )
            with download_cols[1]:
                st.download_button(
                    "下载 HTML 报告",
                    data=build_html_report(bundle, data_quality=data_quality),
                    file_name="multi_agent_causal_report.html",
                    mime="text/html",
                )
            with download_cols[2]:
                if is_pdf_export_available():
                    try:
                        pdf_report = build_pdf_report(bundle, data_quality=data_quality)
                    except PDFExportUnavailableError as exc:
                        st.info(f"Optional PDF export is unavailable: {exc}")
                    else:
                        st.download_button(
                            "下载 PDF 报告",
                            data=pdf_report,
                            file_name="multi_agent_causal_report.pdf",
                            mime="application/pdf",
                        )
                else:
                    st.info(
                        "Optional PDF export requires reportlab. Install with:\n"
                        "`.\\.venv\\Scripts\\python.exe -m pip install -r requirements-pdf.txt`"
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
