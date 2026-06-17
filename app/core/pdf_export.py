from __future__ import annotations

from html import escape
from importlib.util import find_spec
from io import BytesIO
from typing import Any, Iterable

from app.core.schemas import PipelineBundle


class PDFExportUnavailableError(RuntimeError):
    """Raised when optional ReportLab PDF export dependencies are unavailable."""


def is_pdf_export_available() -> bool:
    return find_spec("reportlab") is not None


def build_pdf_report(bundle: PipelineBundle, data_quality: dict[str, Any] | None = None) -> bytes:
    if not is_pdf_export_available():
        raise PDFExportUnavailableError(
            "Optional PDF export requires reportlab. Install requirements-pdf.txt to enable it."
        )

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise PDFExportUnavailableError("ReportLab could not be imported.") from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="Multi-Agent Causal Analytics Team Report",
    )
    styles = getSampleStyleSheet()
    _configure_cjk_font(styles, pdfmetrics, UnicodeCIDFont)
    story: list[Any] = []

    def heading(text: str) -> None:
        story.append(Spacer(1, 10))
        story.append(Paragraph(_pdf_escape(text), styles["Heading2"]))

    def paragraph(text: Any) -> None:
        story.append(Paragraph(_pdf_escape(_stringify(text)), styles["BodyText"]))

    story.append(Paragraph("Multi-Agent Causal Analytics Team Report", styles["Title"]))
    paragraph("Report Polish and Optional PDF Export")
    story.append(Spacer(1, 12))

    heading("User question")
    paragraph(bundle.request.question)

    heading("Variable configuration")
    _add_key_value_table(
        story,
        [
            ("Treatment", bundle.request.treatment),
            ("Outcome", bundle.request.outcome),
            ("Confounders", _join_or_none(bundle.request.confounders)),
            ("Effect modifiers", _join_or_none(bundle.request.effect_modifiers)),
        ],
        styles,
        Table,
        TableStyle,
        colors,
    )

    heading("Estimated ATE")
    estimate = bundle.estimate
    _add_key_value_table(
        story,
        [
            ("Status", estimate.status if estimate else "N/A"),
            ("Method", estimate.method if estimate else "N/A"),
            ("ATE", _format_number(estimate.ate) if estimate else "N/A"),
            (
                "Confidence interval",
                _format_interval(estimate.confidence_intervals) if estimate else "N/A",
            ),
        ],
        styles,
        Table,
        TableStyle,
        colors,
    )

    heading("CATE status")
    cate = bundle.cate
    _add_key_value_table(
        story,
        [
            ("Status", cate.status if cate else "N/A"),
            ("Method", cate.method if cate else "N/A"),
            ("CATE mean", _format_number(cate.cate_mean) if cate else "N/A"),
            ("CATE std", _format_number(cate.cate_std) if cate else "N/A"),
        ],
        styles,
        Table,
        TableStyle,
        colors,
    )

    heading("Data Quality Summary")
    _add_data_quality(story, data_quality, styles, Table, TableStyle, colors)

    heading("Refutation Results")
    _add_refutations(story, bundle.estimate.refutations if bundle.estimate else {}, styles, Table, TableStyle, colors)

    heading("Reviewer Warnings")
    review_warnings = bundle.review.warnings if bundle.review else []
    _add_list_or_message(story, review_warnings, "No reviewer warnings.", styles)

    heading("Caveats / Limitations")
    _add_list_or_message(
        story,
        [
            "This report depends on user-selected causal variables and assumptions.",
            "Refutation checks increase robustness awareness but do not prove causal identification.",
            "EconML CATE and ReportLab PDF export are optional dependencies.",
            "LLM-assisted features are optional and should not be treated as automatic causal discovery.",
        ],
        "No caveats available.",
        styles,
    )

    doc.build(story)
    return buffer.getvalue()


def _add_data_quality(
    story: list[Any],
    data_quality: dict[str, Any] | None,
    styles: Any,
    table_cls: Any,
    table_style_cls: Any,
    colors_module: Any,
) -> None:
    if not data_quality:
        story.append(Paragraph("No data quality summary was provided.", styles["BodyText"]))
        return

    summary = data_quality.get("summary", {})
    treatment_quality = data_quality.get("treatment_quality", {})
    outcome_quality = data_quality.get("outcome_quality", {})
    selected_quality = data_quality.get("selected_variables_quality", {})
    _add_key_value_table(
        story,
        [
            ("Status", data_quality.get("status", "unknown")),
            ("Rows", summary.get("row_count", 0)),
            ("Columns", summary.get("column_count", 0)),
            ("Overall missing rate", _format_rate(summary.get("overall_missing_rate"))),
            ("Duplicate rows", summary.get("duplicate_rows_count", 0)),
            ("Treatment groups", _format_mapping(treatment_quality.get("group_counts", {}))),
            ("Outcome missing rate", _format_rate(outcome_quality.get("missing_rate"))),
            ("Complete-case rows", selected_quality.get("selected_complete_case_count", 0)),
        ],
        styles,
        table_cls,
        table_style_cls,
        colors_module,
    )
    _add_list_or_message(
        story,
        data_quality.get("warnings", []),
        "No major data quality warnings.",
        styles,
    )


def _add_refutations(
    story: list[Any],
    refutations: dict[str, Any],
    styles: Any,
    table_cls: Any,
    table_style_cls: Any,
    colors_module: Any,
) -> None:
    if not refutations:
        story.append(Paragraph("No refutation results available.", styles["BodyText"]))
        return

    rows = [("Refutation", "Status", "New effect", "p-value")]
    for name, payload in refutations.items():
        if isinstance(payload, dict):
            rows.append(
                (
                    name,
                    payload.get("status", "available"),
                    _format_number(payload.get("new_effect")),
                    _format_number(payload.get("p_value")),
                )
            )
        else:
            rows.append((name, "available", "N/A", "N/A"))
    _add_table(story, rows, styles, table_cls, table_style_cls, colors_module)


def _add_key_value_table(
    story: list[Any],
    rows: Iterable[tuple[str, Any]],
    styles: Any,
    table_cls: Any,
    table_style_cls: Any,
    colors_module: Any,
) -> None:
    _add_table(story, rows, styles, table_cls, table_style_cls, colors_module)


def _add_table(
    story: list[Any],
    rows: Iterable[tuple[Any, ...]],
    styles: Any,
    table_cls: Any,
    table_style_cls: Any,
    colors_module: Any,
) -> None:
    data = [
        [Paragraph(_pdf_escape(_stringify(cell)), styles["BodyText"]) for cell in row]
        for row in rows
    ]
    table = table_cls(data, hAlign="LEFT", colWidths=None)
    table.setStyle(
        table_style_cls(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors_module.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors_module.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors_module.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)


def _add_list_or_message(story: list[Any], items: Iterable[Any], message: str, styles: Any) -> None:
    values = [item for item in items if item]
    if not values:
        story.append(Paragraph(_pdf_escape(message), styles["BodyText"]))
        return
    for item in values:
        story.append(Paragraph(f"- {_pdf_escape(_stringify(item))}", styles["BodyText"]))


def _configure_cjk_font(styles: Any, pdfmetrics: Any, unicode_cid_font_cls: Any) -> None:
    try:
        pdfmetrics.registerFont(unicode_cid_font_cls("STSong-Light"))
    except Exception:
        return
    for style in styles.byName.values():
        style.fontName = "STSong-Light"


def _pdf_escape(value: str) -> str:
    return escape(value, quote=True)


def _stringify(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value)


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


def _format_rate(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "N/A"


def _format_mapping(payload: dict[str, Any]) -> str:
    if not payload:
        return "None"
    return ", ".join(f"{key}: {value}" for key, value in payload.items())
