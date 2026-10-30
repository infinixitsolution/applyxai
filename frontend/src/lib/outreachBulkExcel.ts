import * as XLSX from "xlsx";

const NAME_HEADERS = new Set([
  "name",
  "institute",
  "institute name",
  "organization",
  "organisation",
  "company",
  "college",
  "school",
  "contact name",
]);

const EMAIL_HEADERS = new Set(["email", "e-mail", "mail", "email address", "e mail"]);

const PHONE_HEADERS = new Set([
  "phone",
  "mobile",
  "whatsapp",
  "tel",
  "telephone",
  "phone number",
  "mobile number",
  "contact number",
  "contact",
]);

function cellStr(value: unknown): string {
  if (value == null || value === "") return "";
  if (typeof value === "number" && Number.isFinite(value)) {
    const asInt = Math.trunc(value);
    if (asInt === value && String(asInt).length >= 10) return String(asInt);
  }
  return String(value).trim();
}

function headerKey(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, " ");
}

function columnMap(headerRow: unknown[]): { name: number; email: number; phone: number } | null {
  const keys = headerRow.map((c) => headerKey(cellStr(c)));
  if (!keys.some(Boolean)) return null;
  let name = -1;
  let email = -1;
  let phone = -1;
  keys.forEach((key, i) => {
    if (!key) return;
    if (NAME_HEADERS.has(key) && name < 0) name = i;
    if (EMAIL_HEADERS.has(key) && email < 0) email = i;
    if (PHONE_HEADERS.has(key) && phone < 0) phone = i;
  });
  if (email < 0 && phone < 0) return null;
  return { name, email, phone };
}

function rowToContactLine(cells: unknown[], cols: { name: number; email: number; phone: number } | null): string {
  if (cols) {
    const name = cols.name >= 0 ? cellStr(cells[cols.name]) : "";
    const email = cols.email >= 0 ? cellStr(cells[cols.email]) : "";
    const phone = cols.phone >= 0 ? cellStr(cells[cols.phone]) : "";
    const contact = email || phone;
    if (!contact) return "";
    return name ? `${name}, ${contact}` : contact;
  }

  const parts = cells.map(cellStr).filter(Boolean);
  if (!parts.length) return "";
  if (parts.length === 1) return parts[0];
  const hasEmail = parts.some((p) => p.includes("@"));
  const hasPhone = parts.some((p) => /\d{10,}/.test(p.replace(/\D/g, "")));
  if (hasEmail || hasPhone) {
    const contact = parts.find((p) => p.includes("@")) || parts.find((p) => /\d{10,}/.test(p.replace(/\D/g, ""))) || parts[parts.length - 1];
    const name = parts.find((p) => p !== contact) || "";
    return name ? `${name}, ${contact}` : contact;
  }
  return parts.join(", ");
}

/** Parse first worksheet from .xlsx / .xls / .csv into contact lines for bulk import. */
export function contactsFromSpreadsheetBuffer(data: ArrayBuffer): { lines: string[] } {
  const workbook = XLSX.read(data, { type: "array" });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) return { lines: [] };

  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" }) as unknown[][];
  if (!rows.length) return { lines: [] };

  const cols = columnMap(rows[0]);
  const start = cols ? 1 : 0;
  const lines: string[] = [];

  for (let i = start; i < rows.length; i += 1) {
    const line = rowToContactLine(rows[i], cols);
    if (line) lines.push(line);
  }

  return { lines };
}

export const OUTREACH_BULK_SHEET_ACCEPT = ".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv";
