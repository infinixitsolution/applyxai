import { sanitizeLegalHtml } from "./htmlContent";

/** Plain outreach / WhatsApp copy → minimal HTML for the rich editor. */
export function plainTextToEditorHtml(text: string): string {
  const raw = (text || "").trim();
  if (!raw) return "";
  if (/<[a-z][\s\S]*>/i.test(raw)) return sanitizeLegalHtml(raw);
  return raw
    .split(/\n\n+/)
    .map((block) => {
      const escaped = block
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return `<p>${escaped.replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

/** Rich editor HTML → plain text for WhatsApp and plain email fields. */
export function editorHtmlToPlainText(html: string): string {
  if (typeof document === "undefined") return html.replace(/<[^>]+>/g, " ").trim();
  const div = document.createElement("div");
  div.innerHTML = sanitizeLegalHtml(html);
  return (div.innerText || div.textContent || "").replace(/\u00a0/g, " ").trim();
}
