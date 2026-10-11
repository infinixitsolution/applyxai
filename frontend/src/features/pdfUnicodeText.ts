/**
 * Helvetica in jsPDF only covers WinAnsi, and jsPDF does not shape Indic or Arabic text.
 * Latin lines use embedded Noto Sans. Other scripts are painted, with an invisible text layer in a matching font so they can still be selected.
 */

export const PDF_FONTS = [
  { name: "NotoSans", file: "NotoSans-Regular.ttf" },
  { name: "NotoSansDevanagari", file: "NotoSansDevanagari-Regular.ttf" },
  { name: "NotoSansTamil", file: "NotoSansTamil-Regular.ttf" },
  { name: "NotoSansTelugu", file: "NotoSansTelugu-Regular.ttf" },
  { name: "NotoSansGujarati", file: "NotoSansGujarati-Regular.ttf" },
  { name: "NotoSansArabic", file: "NotoSansArabic-Regular.ttf" },
] as const;

export type PdfFontName = (typeof PDF_FONTS)[number]["name"];

export type PdfRun = { text: string; font: PdfFontName };

export type PdfTextImage = {
  dataUrl: string;
  widthMm: number;
  heightMm: number;
  lines: string[];
  lineHeightMm: number;
};

const PX_PER_MM = 96 / 25.4;

export function normalizePdfText(text: string): string {
  return text
    .replace(/[\u2018\u2019\u201A\u2032]/g, "'")
    .replace(/[\u201C\u201D\u201E]/g, '"')
    .replace(/[\u2013\u2014\u2212]/g, "-")
    .replace(/\u2026/g, "...")
    .replace(/\u00A0/g, " ")
    .replace(/\u2022/g, "-")
    .replace(/\r\n?/g, "\n")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
}

export function textNeedsRaster(text: string): boolean {
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    if (cp > 0xff) return true;
  }
  return false;
}

export function pdfFontForCodePoint(cp: number): PdfFontName | null {
  if (cp === 0x0a || cp === 0x09) return "NotoSans";
  if (cp <= 0x024f || (cp >= 0x2000 && cp <= 0x206f)) return "NotoSans";
  if (cp >= 0x0900 && cp <= 0x097f) return "NotoSansDevanagari";
  if (cp >= 0x0a80 && cp <= 0x0aff) return "NotoSansGujarati";
  if (cp >= 0x0b80 && cp <= 0x0bff) return "NotoSansTamil";
  if (cp >= 0x0c00 && cp <= 0x0c7f) return "NotoSansTelugu";
  if ((cp >= 0x0600 && cp <= 0x06ff) || (cp >= 0x0750 && cp <= 0x077f) || (cp >= 0xfb50 && cp <= 0xfdff)) {
    return "NotoSansArabic";
  }
  if (cp > 0xff) return null;
  return "NotoSans";
}

export function textUsesEmbeddedFonts(text: string, loaded: ReadonlySet<string>): boolean {
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    if (cp === 0x0a) continue;
    const font = pdfFontForCodePoint(cp);
    if (!font || !loaded.has(font)) return false;
  }
  return true;
}

/** jsPDF does not shape text, so only scripts that need no shaping can be drawn as visible text. */
export function textDrawsWithoutShaping(text: string, loaded: ReadonlySet<string>): boolean {
  if (!loaded.has("NotoSans")) return false;
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    if (cp === 0x0a) continue;
    if (pdfFontForCodePoint(cp) !== "NotoSans") return false;
  }
  return true;
}

export function wrapPdfLines(
  text: string,
  maxWidth: number,
  measure: (text: string, font: PdfFontName) => number,
  loaded?: ReadonlySet<string>,
): PdfRun[][] {
  const fontOf = (glyph: string) => {
    const font = pdfFontForCodePoint(glyph.codePointAt(0) ?? 0);
    return font && (!loaded || loaded.has(font)) ? font : null;
  };
  return wrapWords(text, maxWidth, fontOf, measure).filter((line) => line.length > 0);
}

/** Wraps at spaces, and only splits a word when it is wider than a whole line. */
function wrapWords<F>(
  text: string,
  maxWidth: number,
  fontOf: (glyph: string) => F | null,
  measure: (text: string, font: F) => number,
): { text: string; font: F }[][] {
  type Piece = { text: string; font: F; width: number };
  const lines: { text: string; font: F }[][] = [[]];
  let width = 0;
  const push = (piece: Piece) => {
    const line = lines[lines.length - 1];
    const last = line[line.length - 1];
    if (last && last.font === piece.font) last.text += piece.text;
    else line.push({ text: piece.text, font: piece.font });
    width += piece.width;
  };
  const newLine = () => {
    lines.push([]);
    width = 0;
  };
  for (const token of text.match(/\n|[^\S\n]+|[^\s]+/g) ?? []) {
    if (token === "\n") {
      newLine();
      continue;
    }
    const pieces: Piece[] = [];
    for (const glyph of graphemes(token)) {
      const font = fontOf(glyph);
      if (font === null) continue;
      pieces.push({ text: glyph, font, width: measure(glyph, font) });
    }
    if (!pieces.length) continue;
    const tokenWidth = pieces.reduce((sum, piece) => sum + piece.width, 0);
    if (/^\s+$/.test(token)) {
      if (width > 0) pieces.forEach(push);
      continue;
    }
    if (width > 0 && width + tokenWidth > maxWidth) newLine();
    for (const piece of pieces) {
      if (width > 0 && width + piece.width > maxWidth) newLine();
      push(piece);
    }
  }
  return lines;
}

function fontFor(cp: number): string {
  if (cp >= 0x0900 && cp <= 0x0dff) return '"Nirmala UI", "Noto Sans", sans-serif';
  if ((cp >= 0x0600 && cp <= 0x06ff) || (cp >= 0x0750 && cp <= 0x077f) || (cp >= 0xfb50 && cp <= 0xfdff)) {
    return '"Segoe UI", "Arial", "Noto Naskh Arabic", sans-serif';
  }
  if ((cp >= 0xac00 && cp <= 0xd7a3) || (cp >= 0x1100 && cp <= 0x11ff)) {
    return '"Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif';
  }
  if ((cp >= 0x3040 && cp <= 0x30ff) || (cp >= 0x4e00 && cp <= 0x9fff) || (cp >= 0x3400 && cp <= 0x4dbf)) {
    return '"Yu Gothic UI", "Yu Gothic", "Hiragino Sans", "MS Gothic", sans-serif';
  }
  if (cp >= 0x1f000 || (cp >= 0x2600 && cp <= 0x27bf)) {
    return '"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
  }
  return '"Segoe UI", Helvetica, Arial, sans-serif';
}

type Run = { text: string; font: string };

function graphemes(text: string): string[] {
  const Segmenter = Intl.Segmenter;
  if (typeof Segmenter === "function") {
    return [...new Segmenter(undefined, { granularity: "grapheme" }).segment(text)].map((part) => part.segment);
  }
  return [...text];
}

function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxWidthPx: number, fontPx: number): Run[][] {
  const lines = wrapWords(
    text,
    maxWidthPx,
    (glyph) => fontFor(glyph.codePointAt(0) ?? 0),
    (glyph, font) => {
      ctx.font = `${fontPx}px ${font}`;
      return ctx.measureText(glyph).width;
    },
  );
  return lines.filter((line, index) => line.length > 0 || index < lines.length - 1);
}

export function rasterizePdfText(text: string, maxWidthMm: number, fontPt = 8.5): PdfTextImage {
  const canvas = document.createElement("canvas");
  const measure = canvas.getContext("2d");
  if (!measure) throw new Error("Could not draw report text.");
  const fontPx = fontPt * (96 / 72);
  const maxWidthPx = Math.max(40, maxWidthMm * PX_PER_MM - 2);
  const lines = wrapLines(measure, text, maxWidthPx, fontPx);
  const lineHeight = fontPx * 1.4;
  let widest = 1;
  for (const line of lines) {
    let lineWidth = 0;
    for (const run of line) {
      measure.font = `${fontPx}px ${run.font}`;
      lineWidth += measure.measureText(run.text).width;
    }
    widest = Math.max(widest, lineWidth);
  }
  const widthPx = Math.max(1, Math.ceil(Math.min(maxWidthPx, widest + 4)));
  const heightPx = Math.max(1, Math.ceil(Math.max(lines.length, 1) * lineHeight));
  const scale = 1.5;
  canvas.width = widthPx * scale;
  canvas.height = heightPx * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Could not draw report text.");
  ctx.scale(scale, scale);
  ctx.fillStyle = "#334155";
  ctx.textBaseline = "top";
  lines.forEach((line, index) => {
    let x = 0;
    const y = index * lineHeight;
    for (const run of line) {
      ctx.font = `${fontPx}px ${run.font}`;
      const arabic = /[\u0600-\u06FF]/.test(run.text);
      ctx.direction = arabic ? "rtl" : "ltr";
      ctx.fillText(run.text, x, y);
      x += ctx.measureText(run.text).width;
    }
  });
  return {
    dataUrl: canvas.toDataURL("image/png"),
    widthMm: widthPx / PX_PER_MM,
    heightMm: heightPx / PX_PER_MM,
    lines: lines.map((line) => line.map((run) => run.text).join("")),
    lineHeightMm: lineHeight / PX_PER_MM,
  };
}
