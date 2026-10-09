/** Web font stacks matching backend DOCX template fonts. */
const STACKS: Record<string, string> = {
  "Times New Roman": '"Times New Roman", Times, Georgia, serif',
  Calibri: 'Calibri, "Segoe UI", Tahoma, sans-serif',
  "Calibri Light": 'Calibri, "Segoe UI Light", "Segoe UI", sans-serif',
  Cambria: 'Cambria, Georgia, "Times New Roman", serif',
  Arial: 'Arial, Helvetica, sans-serif',
  Georgia: 'Georgia, "Times New Roman", serif',
  Consolas: 'Consolas, "Courier New", monospace',
  Verdana: 'Verdana, Geneva, sans-serif',
};

export function templateFontStack(fontName: string): string {
  return STACKS[fontName] ?? `"${fontName}", system-ui, sans-serif`;
}
