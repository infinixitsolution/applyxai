import { describe, expect, it } from "vitest";
import { normalizePdfText, pdfFontForCodePoint, textDrawsWithoutShaping, textNeedsRaster, textUsesEmbeddedFonts, wrapPdfLines } from "./pdfUnicodeText";

describe("pdf unicode text", () => {
  it("turns typographic punctuation into characters Helvetica can draw", () => {
    expect(normalizePdfText("I’m a DevOps engineer…")).toBe("I'm a DevOps engineer...");
  });

  it("keeps plain English as normal PDF text", () => {
    expect(textNeedsRaster("See you later.")).toBe(false);
  });

  it("flags Hindi so it is not written with the Latin font", () => {
    expect(textNeedsRaster("मैं एक DevOps engineer हूँ")).toBe(true);
  });

  it("draws Hindi with the Devanagari font and leaves Korean to be painted", () => {
    const loaded = new Set(["NotoSans", "NotoSansDevanagari"]);
    expect(pdfFontForCodePoint("म".codePointAt(0) ?? 0)).toBe("NotoSansDevanagari");
    expect(textUsesEmbeddedFonts("मैं एक DevOps engineer हूँ", loaded)).toBe(true);
    expect(textUsesEmbeddedFonts("뉴스", loaded)).toBe(false);
  });

  it("wraps at spaces instead of inside words", () => {
    const lines = wrapPdfLines("I can adapt quickly", 7, (text) => text.length);
    expect(lines.map((line) => line.map((run) => run.text).join("").trim())).toEqual(["I can", "adapt", "quickly"]);
  });

  it("draws accented Latin as text and leaves scripts that need shaping to be painted", () => {
    const loaded = new Set(["NotoSans", "NotoSansDevanagari"]);
    expect(textDrawsWithoutShaping("Napisy stworzone przez społeczność", loaded)).toBe(true);
    expect(textDrawsWithoutShaping("मैं एक DevOps engineer हूँ", loaded)).toBe(false);
  });
});
