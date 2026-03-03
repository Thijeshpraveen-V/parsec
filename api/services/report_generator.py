from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional

def generate_pdf_report(analysis: Dict, ai_fixes: Optional[Dict[int, str]] = None) -> BytesIO:
    if ai_fixes is None:
        ai_fixes = {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#0969da"),
        spaceAfter=6, alignment=TA_CENTER
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor("#238636"),
        spaceBefore=14, spaceAfter=6
    )
    h3_style = ParagraphStyle(
        "H3", parent=styles["Heading3"],
        fontSize=11, textColor=colors.HexColor("#6e7781"),
        spaceBefore=8, spaceAfter=4
    )
    ai_fix_style = ParagraphStyle(
        "AIFix", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#1a7f37"),
        backColor=colors.HexColor("#dafbe1"),
        borderPad=6, leading=13, spaceAfter=8,
        leftIndent=8, rightIndent=8,
    )
    warn_style = ParagraphStyle(
        "Warn", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#9a6700"),
    )
    err_style = ParagraphStyle(
        "Err", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#cf222e"),
    )
    normal = styles["Normal"]
    normal.fontSize = 10

    story = []

    # ── Title ──────────────────────────────────────
    story.append(Paragraph("Dependency Analysis Report", title_style))
    story.append(Paragraph(
        f"Repo: <b>{analysis['repo']['owner']}/{analysis['repo']['repo']}</b>",
        ParagraphStyle("sub", parent=normal, alignment=TA_CENTER, fontSize=12)
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M IST')}",
        ParagraphStyle("date", parent=normal, alignment=TA_CENTER,
                       textColor=colors.grey, fontSize=9)
    ))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#d0d7de"), spaceAfter=12))

    # ── Summary ─────────────────────────────────────
    story.append(Paragraph("Summary", h2_style))
    summary_data = [
        ["Total Dependencies", str(len(analysis.get("dependencies", [])))],
        ["Dependency Files", ", ".join(analysis.get("dependency_files", []))],
        ["Breaking Changes", str(len(analysis.get("breaking_changes", [])))],
        ["AI Fixes Generated", str(len(ai_fixes))],
        ["Branch", analysis["repo"].get("branch", "main")],
    ]
    summary_table = Table(summary_data, colWidths=[2.5*inch, 4*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f6f8fa")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#24292f")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # ── Dependencies ────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#d0d7de")))
    story.append(Paragraph("Dependencies", h2_style))

    dep_data = [["Package", "Version", "Source File"]]
    for dep in analysis.get("dependencies", []):
        dep_data.append([
            dep.get("name", ""),
            dep.get("version_spec", "latest"),
            dep.get("file", ""),
        ])

    dep_table = Table(dep_data, colWidths=[2.2*inch, 1.8*inch, 3*inch])
    dep_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0969da")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (1, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(dep_table)
    story.append(Spacer(1, 12))

    # ── Breaking Changes ─────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#d0d7de")))
    story.append(Paragraph("Breaking Changes", h2_style))

    breaking = analysis.get("breaking_changes", [])
    if not breaking:
        story.append(Paragraph("No packages analysed.", normal))
    else:
        for i, b in enumerate(breaking):
            pkg = b.get("package", "unknown")

            # Determine the Griffe note (small subtitle)
            if b.get("error"):
                griffe_note = f"Analysis note: {b['error'][:120]}"
            elif b.get("info"):
                griffe_note = b["info"]
            else:
                griffe_note = (
                    f"Kind: {b.get('kind', 'N/A')} | "
                    f"Location: {b.get('location', 'N/A')} | "
                    f"Reason: {b.get('reason', 'N/A')}"
                )

            # Package heading
            story.append(Paragraph(f"<b>{pkg}</b>", h3_style))

            # Small Griffe note in grey
            story.append(Paragraph(
                griffe_note,
                ParagraphStyle("gnote", parent=normal,
                               fontSize=8, textColor=colors.grey,
                               spaceAfter=4)
            ))

            # AI suggestion as the main block
            if i in ai_fixes and ai_fixes[i]:
                fix_text = (ai_fixes[i]
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;"))
                story.append(Paragraph(
                    f"<b>AI Suggestion:</b><br/>{fix_text}",
                    ai_fix_style
                ))
            else:
                story.append(Paragraph(
                    "AI suggestion not available for this package.",
                    ParagraphStyle("nai", parent=normal,
                                   fontSize=9, textColor=colors.grey)
                ))

            story.append(Spacer(1, 10))


    story.append(Spacer(1, 12))

    # ── Footer ──────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#d0d7de")))
    story.append(Paragraph(
        "Generated by <b>Parsec — Dependency Analyser</b> | "
        "Powered by Griffe + Astra DB + Groq LLaMA-3.3",
        ParagraphStyle("footer", parent=normal, alignment=TA_CENTER,
                       textColor=colors.grey, fontSize=8)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
