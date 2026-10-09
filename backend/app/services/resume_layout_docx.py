"""Paragraph-level layout accents for resume template export."""

from __future__ import annotations

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph

from backend.app.services import resume_text_service


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _bottom_border(paragraph: Paragraph, *, color: str, size: int = 8) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _left_border(paragraph: Paragraph, *, color: str, size: int = 16) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(size))
    left.set(qn("w:color"), color)
    left.set(qn("w:space"), "4")
    p_bdr.append(left)
    p_pr.append(p_bdr)


def _shading(paragraph: Paragraph, *, fill: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def _section_ranges(paragraphs: list[Paragraph]) -> dict[str, tuple[int, int]]:
    headers: list[tuple[int, str]] = []
    for i, para in enumerate(paragraphs):
        kind = resume_text_service.section_kind(para.text)
        if kind:
            headers.append((i, kind))
    ranges: dict[str, tuple[int, int]] = {}
    for idx, (start_i, kind) in enumerate(headers):
        end_i = headers[idx + 1][0] if idx + 1 < len(headers) else len(paragraphs)
        ranges[kind] = (start_i, end_i)
    return ranges


def apply_layout(doc: Document, layout: str, *, accent_rgb: tuple[int, int, int]) -> None:
    paragraphs = list(doc.paragraphs)
    if not paragraphs:
        return
    accent = _rgb_hex(accent_rgb)
    first_section_idx = next(
        (i for i, p in enumerate(paragraphs) if resume_text_service.section_kind(p.text)),
        len(paragraphs),
    )
    name_idx = next((i for i, p in enumerate(paragraphs[:first_section_idx]) if p.text.strip()), None)
    sections = _section_ranges(paragraphs)

    if layout == "ruled_underline":
        for i, para in enumerate(paragraphs):
            if resume_text_service.section_kind(para.text):
                _bottom_border(para, color=accent, size=6)
                para.paragraph_format.space_after = Pt(4)

    elif layout == "left_accent_bar":
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                _left_border(para, color=accent, size=20)
                para.paragraph_format.left_indent = Inches(0.08)

    elif layout == "airy_divider":
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                para.paragraph_format.space_before = Pt(14)
                _bottom_border(para, color="E2E8F0", size=4)
            else:
                para.paragraph_format.space_after = Pt(8)

    elif layout == "centered_name":
        if name_idx is not None:
            paragraphs[name_idx].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                _bottom_border(para, color=accent, size=6)

    elif layout == "tight_blocks":
        for para in paragraphs:
            pf = para.paragraph_format
            pf.space_before = Pt(0)
            pf.space_after = Pt(2)
            if resume_text_service.section_kind(para.text):
                pf.space_before = Pt(6)

    elif layout == "centered_serif":
        if name_idx is not None:
            paragraphs[name_idx].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                for run in para.runs:
                    run.italic = True

    elif layout == "name_banner":
        if name_idx is not None:
            banner = paragraphs[name_idx]
            _shading(banner, fill=accent)
            for run in banner.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
            banner.paragraph_format.space_after = Pt(10)
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                for run in para.runs:
                    run.font.all_caps = True

    elif layout == "skills_panel":
        skills = sections.get("skills")
        if skills:
            start, end = skills
            for idx in range(start + 1, end):
                if idx < len(paragraphs) and paragraphs[idx].text.strip():
                    _shading(paragraphs[idx], fill="F1F5F9")
                    paragraphs[idx].paragraph_format.left_indent = Inches(0.12)
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                _left_border(para, color=accent, size=12)

    elif layout == "margin_stripe":
        for para in paragraphs:
            if not resume_text_service.section_kind(para.text) and para.text.strip():
                _left_border(para, color=accent, size=8)
                para.paragraph_format.left_indent = Inches(0.14)

    elif layout == "executive_split":
        if name_idx is not None:
            paragraphs[name_idx].alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        if name_idx is not None and name_idx + 1 < first_section_idx:
            contact = paragraphs[name_idx + 1]
            contact.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        for para in paragraphs:
            if resume_text_service.section_kind(para.text):
                _bottom_border(para, color="CBD5E1", size=4)
                para.paragraph_format.space_before = Pt(10)
