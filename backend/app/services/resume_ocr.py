"""OCR for scanned or image-only PDF resumes (ONNX via RapidOCR, render via PyMuPDF)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_USABLE_CHARS = 120
MIN_ALNUM_RATIO = 0.25
_OCR = None


def _ocr_engine():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR = RapidOCR()
    return _OCR


def text_usable(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < MIN_USABLE_CHARS:
        return False
    alnum = sum(1 for c in t if c.isalnum())
    return alnum >= max(MIN_USABLE_CHARS * MIN_ALNUM_RATIO, 40)


def ocr_pdf(path: Path, *, scale: float = 2.0, max_pages: int = 12) -> str:
    import fitz
    import numpy as np

    engine = _ocr_engine()
    lines: list[str] = []
    with fitz.open(str(path)) as doc:
        for page in doc[:max_pages]:
            matrix = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            channels = pix.n
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, channels)
            if channels == 4:
                img = img[:, :, :3]
            result, _ = engine(img)
            if not result:
                continue
            for row in result:
                if len(row) > 1 and str(row[1]).strip():
                    lines.append(str(row[1]).strip())
    return "\n".join(lines).strip()


def merge_pdf_text(native: str, ocr: str) -> str:
    """Prefer OCR when native is weak; otherwise combine unique blocks."""
    native = (native or "").strip()
    ocr = (ocr or "").strip()
    if not ocr:
        return native
    if not native or not text_usable(native):
        return ocr
    if len(ocr) > len(native) * 1.15:
        return ocr
    return f"{native}\n\n{ocr}".strip()
