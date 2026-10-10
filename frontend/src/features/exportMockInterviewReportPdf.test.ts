import { describe, expect, it, vi } from "vitest";
import type { MockInterviewFeedback, MockInterviewSessionDetail } from "../types";
import { exportMockInterviewReportPdf, mockInterviewReportPdfFilename } from "./exportMockInterviewReportPdf";

vi.mock("./pdfApplyXaiBranding", () => ({
  loadApplyXaiMascotDataUrl: vi.fn(async () => "data:image/png;base64,abc"),
  PDF_WATERMARK_TEXT: "ApplyXAI",
}));

const save = vi.fn();
vi.mock("jspdf", () => ({
  jsPDF: class MockJsPDF {
    internal = { pageSize: { getWidth: () => 210, getHeight: () => 297 } };
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
    splitTextToSize = vi.fn((t: string) => [t]);
    getTextWidth = vi.fn(() => 10);
    circle = vi.fn();
    roundedRect = vi.fn();
    setDrawColor = vi.fn();
    setLineWidth = vi.fn();
  },
}));

vi.mock("jspdf-autotable", () => ({ default: vi.fn() }));

const session = {
  id: "sess-1",
  status: "completed",
  application_id: "app-1",
  interview_types: ["behavioral"],
  turn_count: 2,
  context_snapshot: { job_title: "Engineer", company: "Acme" },
  messages: [
    { id: "m1", role: "interviewer", content: "Hello?", created_at: "2026-01-01T00:00:00Z" },
    { id: "m2", role: "candidate", content: "Hi.", created_at: "2026-01-01T00:01:00Z" },
  ],
  feedback: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:05:00Z",
  ends_at: "2026-01-01T01:00:00Z",
  max_duration_seconds: 1800,
  seconds_remaining: null,
} as MockInterviewSessionDetail;

const feedback = {
  overall_score: 62,
  knowledge_summary: "Solid basics.",
  dimensions: [{ key: "communication", label: "Communication", score: 70, notes: "Clear." }],
  question_breakdown: [],
  rubric_scores: [],
} as MockInterviewFeedback;

describe("exportMockInterviewReportPdf", () => {
  it("builds a filename from session context", () => {
    expect(mockInterviewReportPdfFilename(session)).toMatch(/mock-interview/i);
  });

  it("runs export without throwing", async () => {
    await exportMockInterviewReportPdf(session, feedback);
    expect(save).toHaveBeenCalled();
  });
});
