import DOMPurify from "dompurify";
import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: true });

export function looksLikeHtml(content: string): boolean {
  const t = content.trim();
  if (!t) return false;
  if (t.startsWith("<")) return true;
  return /<(?:p|h[1-6]|ul|ol|li|div|br|strong|em|a|blockquote)\b/i.test(t);
}

/** Safe HTML for public legal pages and admin preview. */
export function sanitizeLegalHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  });
}

/** Normalize legacy Markdown to HTML for the visual editor. */
export function contentForLegalEditor(raw: string): string {
  if (!raw.trim()) return "";
  if (looksLikeHtml(raw)) return raw;
  const parsed = marked.parse(raw);
  return typeof parsed === "string" ? parsed : "";
}
