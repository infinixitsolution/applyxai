import { describe, expect, it } from "vitest";
import * as XLSX from "xlsx";
import { contactsFromSpreadsheetBuffer } from "./outreachBulkExcel";

function sheetBuffer(rows: unknown[][]): ArrayBuffer {
  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Leads");
  return XLSX.write(wb, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

describe("contactsFromSpreadsheetBuffer", () => {
  it("reads header row with name, email, phone", () => {
    const buf = sheetBuffer([
      ["Institute Name", "Email", "Mobile"],
      ["Alpha Coaching", "a@alpha.in", "9876543210"],
      ["", "solo@b.com", ""],
    ]);
    const { lines } = contactsFromSpreadsheetBuffer(buf);
    expect(lines).toEqual(["Alpha Coaching, a@alpha.in", "solo@b.com"]);
  });

  it("reads rows without headers", () => {
    const buf = sheetBuffer([["Beta Institute", "beta@test.com"]]);
    const { lines } = contactsFromSpreadsheetBuffer(buf);
    expect(lines).toEqual(["Beta Institute, beta@test.com"]);
  });
});
