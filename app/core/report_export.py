from __future__ import annotations

from html import escape
from typing import Any, Iterable

from app.core.schemas import PipelineBundle


def build_html_report(bundle: PipelineBundle) -> str:
    """Build a self-contained HTML report from a finished PipelineBundle."""
    request = bundle.request
    profile = bundle.profile
    method = bundle.method
    estimate = bundle.estimate
    cate = bundle.cate
    review = bundle.review

    sections = [
        _section(
            "User question",
            f"<p>{_e(request.question)}</p>",
        ),
        _section(
            "Variable configuration",
            _definition_list(
                [
                    ("Treatment", request.treatment),
                    ("Outcome", request.outcome),
                    ("Confounders", _join_or_none(request.confounders)),
                    ("Effect modifiers", _join_or_none(request.effect_modifiers)),
                ]
            ),
        ),
    ]

    if profile:
        sections.append(
            _section(
                "Data profile summary",
                _definition_list(
                    [
                        ("Rows", profile.n_rows),
                        ("Columns", profile.n_cols),
                        ("Numeric columns", _join_or_none(profile.numeric_columns)),
                        ("Categorical columns", _join_or_none(profile.categorical_columns)),
                    ]
                ),
            )
        )

    if method:
        method_body = _definition_list(
            [
                ("Primary method", method.primary),
                ("Secondary method", method.secondary),
            ]
        )
        method_body += _list_block("Assumptions", method.assumptions)
        method_body += _list_block("Warnings", method.warnings)
        sections.append(_section("Method selection", method_body))

    if estimate:
        estimate_body = _definition_list(
            [
                ("Status", estimate.status),
                ("Method", estimate.method),
                ("Estimated ATE", _format_number(estimate.ate)),
                ("Confidence interval", _format_interval(estimate.confidence_intervals)),
            ]
        )
        estimate_body += _list_block("Warnings", estimate.warnings)
        if estimate.error:
            estimate_body += f'<p class="warning">{_e(estimate.error)}</p>'
        sections.append(_section("Estimated ATE", estimate_body))

        sections.append(
            _section(
                "Refutation results",
                _refutations_table(estimate.refutations),
            )
        )

    if cate:
        cate_body = _definition_list(
            [
                ("CATE status", cate.status),
                ("Method", cate.method),
                ("CATE mean", _format_number(cate.cate_mean)),
                ("CATE std", _format_number(cate.cate_std)),
                ("Number of effects", cate.n_effects),
            ]
        )
        cate_body += _key_value_table("Segment summary", cate.segment_summary)
        cate_body += _list_block("Warnings", cate.warnings)
        if cate.error:
            cate_body += f'<p class="warning">{_e(cate.error)}</p>'
        sections.append(_section("CATE status", cate_body))

    if review:
        review_body = _definition_list([("Reviewer status", review.status)])
        review_body += _key_value_table("Reviewer checks", review.checks)
        review_body += _list_block("Reviewer warnings", review.warnings)
        sections.append(_section("Reviewer warnings", review_body))

    sections.append(
        _section(
            "Agent logs summary",
            _agent_logs_table(bundle.agent_logs),
        )
    )
    sections.append(
        _section(
            "Caveats / limitations",
            _list_block(
                "",
                [
                    "This report depends on user-selected causal variables and assumptions.",
                    "Refutation checks increase robustness awareness but do not prove causal identification.",
                    "EconML CATE is optional and may be skipped when dependencies are unavailable.",
                    "LLM-assisted features are optional and should not be treated as automatic causal discovery.",
                ],
            ),
        )
    )

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Multi-Agent Causal Analytics Team Report</title>",
            _style_block(),
            "</head>",
            "<body>",
            '<main class="report">',
            '<p class="eyebrow">Multi-Agent Causal Analytics Team</p>',
            "<h1>Multi-Agent Causal Analytics Team Report</h1>",
            "".join(sections),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _section(title: str, body: str) -> str:
    return f'<section><h2>{_e(title)}</h2>{body}</section>'


def _definition_list(items: Iterable[tuple[str, Any]]) -> str:
    rows = []
    for key, value in items:
        rows.append(f"<dt>{_e(key)}</dt><dd>{_e(value)}</dd>")
    return f"<dl>{''.join(rows)}</dl>"


def _list_block(title: str, items: Iterable[Any]) -> str:
    values = [item for item in items if item]
    if not values:
        return ""
    heading = f"<h3>{_e(title)}</h3>" if title else ""
    lis = "".join(f"<li>{_e(item)}</li>" for item in values)
    return f"{heading}<ul>{lis}</ul>"


def _key_value_table(title: str, payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    rows = "".join(
        f"<tr><th>{_e(key)}</th><td>{_e(value)}</td></tr>"
        for key, value in payload.items()
    )
    return f"<h3>{_e(title)}</h3><table>{rows}</table>"


def _refutations_table(refutations: dict[str, Any]) -> str:
    if not refutations:
        return "<p>No refutation results available.</p>"

    rows = []
    for name, payload in refutations.items():
        if isinstance(payload, dict):
            status = payload.get("status", "available")
            estimated_effect = _format_number(payload.get("estimated_effect"))
            new_effect = _format_number(payload.get("new_effect"))
            difference = _format_number(payload.get("absolute_difference_from_baseline"))
            p_value = _format_number(payload.get("p_value"))
            error = payload.get("error") or ""
        else:
            status = "available"
            estimated_effect = "N/A"
            new_effect = "N/A"
            difference = "N/A"
            p_value = "N/A"
            error = payload
        rows.append(
            "<tr>"
            f"<td>{_e(name)}</td>"
            f"<td>{_e(status)}</td>"
            f"<td>{_e(estimated_effect)}</td>"
            f"<td>{_e(new_effect)}</td>"
            f"<td>{_e(difference)}</td>"
            f"<td>{_e(p_value)}</td>"
            f"<td>{_e(error)}</td>"
            "</tr>"
        )

    return (
        "<table>"
        "<thead><tr><th>Refutation</th><th>Status</th><th>Estimated effect</th>"
        "<th>New effect</th><th>Difference</th><th>p-value</th><th>Error</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _agent_logs_table(agent_logs: list[Any]) -> str:
    if not agent_logs:
        return "<p>No agent logs available.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{_e(log.agent)}</td>"
        f"<td>{_e(log.status)}</td>"
        f"<td>{_e(log.error or '')}</td>"
        "</tr>"
        for log in agent_logs
    )
    return (
        "<table>"
        "<thead><tr><th>Agent</th><th>Status</th><th>Error</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "None selected"


def _format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def _format_interval(values: list[float] | None) -> str:
    if not values or len(values) < 2:
        return "N/A"
    return f"[{_format_number(values[0])}, {_format_number(values[1])}]"


def _style_block() -> str:
    return """
<style>
  body {
    margin: 0;
    background: #f5f7fb;
    color: #18202f;
    font-family: Arial, Helvetica, sans-serif;
    line-height: 1.55;
  }
  .report {
    max-width: 1040px;
    margin: 0 auto;
    padding: 40px 24px 56px;
  }
  .eyebrow {
    color: #4f46e5;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin: 0 0 8px;
    text-transform: uppercase;
  }
  h1 {
    font-size: 34px;
    margin: 0 0 28px;
  }
  h2 {
    border-bottom: 1px solid #d7dcea;
    font-size: 22px;
    margin-top: 0;
    padding-bottom: 8px;
  }
  h3 {
    font-size: 16px;
    margin-bottom: 8px;
  }
  section {
    background: #ffffff;
    border: 1px solid #dfe4ef;
    border-radius: 8px;
    margin: 18px 0;
    padding: 22px;
  }
  dl {
    display: grid;
    grid-template-columns: minmax(150px, 220px) 1fr;
    gap: 8px 16px;
  }
  dt {
    color: #4b5563;
    font-weight: 700;
  }
  dd {
    margin: 0;
  }
  table {
    border-collapse: collapse;
    font-size: 14px;
    margin-top: 10px;
    width: 100%;
  }
  th, td {
    border: 1px solid #dfe4ef;
    padding: 9px 10px;
    text-align: left;
    vertical-align: top;
  }
  th {
    background: #eef2ff;
  }
  .warning {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 6px;
    padding: 10px 12px;
  }
</style>
"""
