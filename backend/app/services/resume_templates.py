"""Ten candidate-facing resume layout styles applied to exported DOCX files."""

from __future__ import annotations

from dataclasses import dataclass

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor

from backend.app.core.errors import AppError
from backend.app.services import resume_text_service

DEFAULT_TEMPLATE_ID = "modern"


@dataclass(frozen=True)
class ResumeTemplateStyle:
    id: str
    name: str
    description: str
    accent: str
    body_font: str
    heading_font: str
    body_pt: int
    heading_pt: int
    name_pt: int
    heading_rgb: tuple[int, int, int]
    body_rgb: tuple[int, int, int]
    margin_in: float
    tight: bool
    layout: str
    layout_label: str


_TEMPLATES: tuple[ResumeTemplateStyle, ...] = (
    ResumeTemplateStyle(
        "classic", "Classic", "Single column with underlined section rules.", "#1e293b",
        "Times New Roman", "Times New Roman", 11, 12, 16, (30, 41, 59), (15, 23, 42), 1.0, False,
        "ruled_underline", "Underlined sections",
    ),
    ResumeTemplateStyle(
        "modern", "Modern", "Left accent bar on each section heading.", "#2563eb",
        "Calibri", "Calibri", 11, 12, 18, (37, 99, 235), (51, 65, 85), 0.85, False,
        "left_accent_bar", "Accent bar",
    ),
    ResumeTemplateStyle(
        "minimal", "Minimal", "Airy spacing with light dividers.", "#64748b",
        "Calibri", "Calibri Light", 11, 11, 17, (100, 116, 139), (71, 85, 105), 1.1, False,
        "airy_divider", "Airy dividers",
    ),
    ResumeTemplateStyle(
        "professional", "Professional", "Centered name and section titles.", "#1e3a8a",
        "Calibri", "Cambria", 11, 12, 18, (30, 58, 138), (30, 41, 59), 0.9, False,
        "centered_name", "Centered header",
    ),
    ResumeTemplateStyle(
        "compact", "Compact", "Dense single-column blocks for one page.", "#334155",
        "Arial", "Arial", 10, 11, 15, (51, 65, 85), (30, 41, 59), 0.65, True,
        "tight_blocks", "Dense blocks",
    ),
    ResumeTemplateStyle(
        "elegant", "Elegant", "Centered name with italic section titles.", "#7c2d12",
        "Georgia", "Georgia", 11, 12, 19, (124, 45, 18), (41, 37, 36), 1.0, False,
        "centered_serif", "Centered elegant",
    ),
    ResumeTemplateStyle(
        "bold", "Bold", "Banner name strip and caps section labels.", "#0f172a",
        "Arial", "Arial", 11, 13, 20, (15, 23, 42), (30, 41, 59), 0.85, False,
        "name_banner", "Name banner",
    ),
    ResumeTemplateStyle(
        "tech", "Tech", "Skills highlighted in a shaded panel.", "#0891b2",
        "Calibri", "Consolas", 11, 12, 18, (8, 145, 178), (51, 65, 85), 0.85, False,
        "skills_panel", "Skills panel",
    ),
    ResumeTemplateStyle(
        "creative", "Creative", "Accent stripe along the left margin.", "#0d9488",
        "Verdana", "Verdana", 11, 12, 19, (13, 148, 136), (55, 65, 81), 1.05, False,
        "margin_stripe", "Side stripe",
    ),
    ResumeTemplateStyle(
        "executive", "Executive", "Split header: name left, contact right.", "#44403c",
        "Cambria", "Cambria", 11, 12, 22, (68, 64, 60), (41, 37, 36), 1.0, False,
        "executive_split", "Split header",
    ),
)

_BY_ID = {t.id: t for t in _TEMPLATES}


def normalize_template_id(template_id: str | None) -> str:
    key = (template_id or DEFAULT_TEMPLATE_ID).strip().lower()
    if key not in _BY_ID:
        raise AppError("VALIDATION", f"Unknown resume template '{template_id}'.", 422)
    return key


def get_template(template_id: str) -> ResumeTemplateStyle:
    return _BY_ID[normalize_template_id(template_id)]


def list_templates() -> list[dict]:
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "accent": t.accent,
            "body_font": t.body_font,
            "heading_font": t.heading_font,
            "layout": t.layout,
            "layout_label": t.layout_label,
        }
        for t in _TEMPLATES
    ]


def preferred_template_for_user(db, user) -> str:
    from sqlalchemy import select

    from backend.app.models import UserProfile

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    raw = getattr(profile, "preferred_resume_template", None) if profile else None
    try:
        return normalize_template_id(raw or DEFAULT_TEMPLATE_ID)
    except AppError:
        return DEFAULT_TEMPLATE_ID


def _style_run(run, *, font: str, size_pt: int, rgb: tuple[int, int, int], bold: bool = False) -> None:
    run.font.name = font
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*rgb)


def apply_template_to_document(doc: Document, template_id: str) -> None:
    style = get_template(template_id)
    paragraphs = doc.paragraphs
    first_section_idx = next(
        (i for i, p in enumerate(paragraphs) if resume_text_service.section_kind(p.text)),
        len(paragraphs),
    )
    name_idx = next((i for i, p in enumerate(paragraphs[:first_section_idx]) if p.text.strip()), None)

    for section in doc.sections:
        section.top_margin = Inches(style.margin_in)
        section.bottom_margin = Inches(style.margin_in)
        section.left_margin = Inches(style.margin_in)
        section.right_margin = Inches(style.margin_in)

    normal = doc.styles["Normal"].font
    normal.name = style.body_font
    normal.size = Pt(style.body_pt)

    for i, para in enumerate(paragraphs):
        text = para.text.strip()
        if not text:
            continue
        kind = resume_text_service.section_kind(text)
        if not para.runs:
            para.add_run(text)
        if kind:
            for run in para.runs:
                _style_run(
                    run,
                    font=style.heading_font,
                    size_pt=style.heading_pt,
                    rgb=style.heading_rgb,
                    bold=True,
                )
        elif name_idx is not None and i == name_idx:
            for run in para.runs:
                _style_run(run, font=style.heading_font, size_pt=style.name_pt, rgb=style.heading_rgb, bold=True)
        else:
            for run in para.runs:
                _style_run(run, font=style.body_font, size_pt=style.body_pt, rgb=style.body_rgb)
        pf = para.paragraph_format
        if style.tight:
            pf.space_before = Pt(0)
            pf.space_after = Pt(2)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        else:
            pf.space_after = Pt(6)
            pf.line_spacing = 1.08

    from backend.app.services.resume_layout_docx import apply_layout

    apply_layout(doc, style.layout, accent_rgb=style.heading_rgb)
