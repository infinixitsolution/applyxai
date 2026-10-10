import { describe, expect, it } from "vitest";
import { contentForLegalEditor, looksLikeHtml, sanitizeLegalHtml } from "./htmlContent";

describe("htmlContent", () => {
  it("detects HTML vs Markdown", () => {
    expect(looksLikeHtml("## Hello")).toBe(false);
    expect(looksLikeHtml("<p>Hello</p>")).toBe(true);
  });

  it("converts Markdown for the editor", () => {
    expect(contentForLegalEditor("## Title\n\nBody")).toContain("<h2");
  });

  it("strips scripts from HTML", () => {
    expect(sanitizeLegalHtml('<p>OK</p><script>alert(1)</script>')).not.toContain("script");
  });
});
