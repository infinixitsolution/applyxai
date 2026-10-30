import { describe, expect, it, vi } from "vitest";
import type { LiveInterviewSession } from "../types";
import { exportLiveInterviewReportPdf, liveInterviewReportPdfFilename } from "./exportLiveInterviewReportPdf";

vi.mock("./pdfApplyXaiBranding", () => ({
  loadApplyXaiMascotDataUrl: vi.fn(async () => "data:image/png;base64,abc"),
  PDF_WATERMARK_TEXT: "ApplyXAI",
}));

const save = vi.fn();
vi.mock("jspdf", () => ({
  jsPDF: class MockJsPDF {
    internal = {
      pageSize: { getWidth: () => 210, getHeight: () => 297 },
      getFontSize: () => 11,
      getFont: () => ({ fontName: "helvetica", fontStyle: "normal" }),
    };
    setFillColor = vi.fn();
    setTextColor = vi.fn();
    setFontSize = vi.fn();
    setFont = vi.fn();
    text = vi.fn();
    addPage = vi.fn();
    rect = vi.fn();
    line = vi.fn();
    save = save;
    getNumberOfPages = vi.fn(() => 1);
    setPage = vi.fn();
    addImage = vi.fn();
    addFileToVFS = vi.fn();
    addFont = vi.fn();
    splitTextToSize = vi.fn((t: string) => [t]);
    getTextWidth = vi.fn(() => 10);
    circle = vi.fn();
    roundedRect = vi.fn();
    setDrawColor = vi.fn();
    setLineWidth = vi.fn();
    lastAutoTable = { finalY: 80 };
  },
}));

vi.mock("jspdf-autotable", () => ({ default: vi.fn() }));

const session = {
  id: "live-1",
  status: "completed",
  job_title: "Staff Engineer",
  company: "Acme Labs",
  application_id: "app-1",
  transcript: [{ role: "interviewer", text: "Hello", at: "2026-01-01T00:00:00Z" }],
  feedback: { overall_score: 70, summary: "Solid.", dimensions: [] },
  started_at: "2026-01-01T00:00:00Z",
  ended_at: "2026-01-01T00:30:00Z",
} as LiveInterviewSession;

describe("exportLiveInterviewReportPdf", () => {
  it("builds a filename from session context", () => {
    expect(liveInterviewReportPdfFilename(session)).toMatch(/live-interview/i);
    expect(liveInterviewReportPdfFilename(session)).toMatch(/Acme/i);
  });

  it("runs export without throwing", async () => {
    await exportLiveInterviewReportPdf(session);
    expect(save).toHaveBeenCalled();
  });
});
