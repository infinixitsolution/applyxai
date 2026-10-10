import type { jsPDF } from "jspdf";
import type { MockInterviewFeedback, MockInterviewSessionDetail } from "../types";
import { APP_NAME } from "../lib/config";
import { formatDateTime } from "../lib/format";
import { loadApplyXaiMascotDataUrl, PDF_WATERMARK_TEXT } from "./pdfApplyXaiBranding";
import { buildMockInterviewReportStats } from "./mockInterviewReportMetrics";

const CONDUCT_LABELS: Record<string, string> = {
  smoking: "Smoking on camera",
  vaping: "Vaping on camera",
  eating: "Eating during interview",
  drinking_alcohol: "Alcohol visible",
  phone_use: "Phone use on camera",
  inappropriate_background: "Unprofessional background",
  off_camera_behavior: "Unprofessional on-camera behavior",
};

const AUTHENTICITY_LABELS: Record<string, string> = {
  human: "Naturally spoken",
  mixed: "Mixed style",
  bookish: "Textbook / formal",
  ai_like: "AI-like phrasing",
  missing: "No answers",
  unknown: "Unknown",
};

const PAGE_W = 210;
const PAGE_H = 297;
const MARGIN = 12;
const CONTENT_W = PAGE_W - MARGIN * 2;
const FOOTER_Y = PAGE_H - 8;

const C = {
  brand: [37, 99, 235] as const,
  brandDark: [29, 78, 216] as const,
  slate900: [15, 23, 42] as const,
  slate700: [51, 65, 85] as const,
  slate500: [100, 116, 139] as const,
  slate200: [226, 232, 240] as const,
  slate50: [248, 250, 252] as const,
  white: [255, 255, 255] as const,
  emerald: [16, 185, 129] as const,
  amber: [245, 158, 11] as const,
  red: [239, 68, 68] as const,
};

type RGB = readonly [number, number, number];

function sanitizeFilename(part: string): string {
  return part.replace(/[^\w\-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "report";
}

export function mockInterviewReportPdfFilename(session: MockInterviewSessionDetail): string {
  const snap = session.context_snapshot;
  const company = sanitizeFilename(snap.company || "session");
  const date = session.updated_at.slice(0, 10);
  return `mock-interview-${company}-${date}.pdf`;
}

function scoreBarColor(score: number): RGB {
  if (score >= 70) return C.emerald;
  if (score >= 45) return C.brand;
  if (score >= 20) return C.amber;
  return C.red;
}

class ReportPdf {
  doc: jsPDF;
  y = MARGIN;
  session: MockInterviewSessionDetail;
  fb: MockInterviewFeedback;
  mascotDataUrl: string | null;

  constructor(
    doc: jsPDF,
    session: MockInterviewSessionDetail,
    fb: MockInterviewFeedback,
    mascotDataUrl: string | null,
  ) {
    this.doc = doc;
    this.session = session;
    this.fb = fb;
    this.mascotDataUrl = mascotDataUrl;
  }

  /** Sidebar-style wordmark on dark header bands. */
  drawApplyXaiWordmark(x: number, y: number, logoMm = 11, fontSize = 14) {
    const d = this.doc;
    let textX = x;
    if (this.mascotDataUrl) {
      d.addImage(this.mascotDataUrl, "PNG", x, y, logoMm, logoMm);
      textX = x + logoMm + 2.5;
    }
    d.setFont("helvetica", "bold");
    d.setFontSize(fontSize);
    d.setTextColor(255, 255, 255);
    d.text("Apply", textX, y + logoMm * 0.62);
    const applyW = d.getTextWidth("Apply");
    d.setTextColor(147, 197, 253);
    d.text("XAI", textX + applyW + 0.4, y + logoMm * 0.62);
  }

  drawPageWatermark() {
    const d = this.doc;
    d.setFont("helvetica", "bold");
    d.setFontSize(52);
    d.setTextColor(241, 245, 249);
    d.text(PDF_WATERMARK_TEXT, PAGE_W / 2, PAGE_H / 2, { align: "center", angle: 38 });
    d.setFontSize(11);
    d.setTextColor(226, 232, 240);
    d.text("Confidential · Mock interview report", PAGE_W / 2, PAGE_H / 2 + 14, { align: "center", angle: 38 });
  }

  private setFill(rgb: RGB) {
    this.doc.setFillColor(rgb[0], rgb[1], rgb[2]);
  }

  private setDraw(rgb: RGB) {
    this.doc.setDrawColor(rgb[0], rgb[1], rgb[2]);
  }

  private setText(rgb: RGB) {
    this.doc.setTextColor(rgb[0], rgb[1], rgb[2]);
  }

  ensureSpace(need: number) {
    if (this.y + need > FOOTER_Y - 4) {
      this.doc.addPage();
      this.drawPageWatermark();
      this.y = MARGIN;
    }
  }

  drawScoreBar(x: number, y: number, width: number, height: number, score: number | null | undefined) {
    const d = this.doc;
    this.setFill(C.slate200);
    d.roundedRect(x, y, width, height, 1, 1, "F");
    if (score == null) return;
    const fillW = (Math.min(100, Math.max(0, score)) / 100) * width;
    if (fillW <= 0) return;
    this.setFill(scoreBarColor(score));
    d.roundedRect(x, y, fillW, height, 1, 1, "F");
  }

  sectionTitle(title: string, subtitle?: string) {
    this.ensureSpace(16);
    const d = this.doc;
    this.setFill(C.brand);
    d.rect(MARGIN, this.y, 3, 8, "F");
    d.setFont("helvetica", "bold");
    d.setFontSize(13);
    this.setText(C.slate900);
    d.text(title, MARGIN + 6, this.y + 5.5);
    this.y += 10;
    if (subtitle) {
      d.setFont("helvetica", "normal");
      d.setFontSize(9);
      this.setText(C.slate500);
      const lines = d.splitTextToSize(subtitle, CONTENT_W);
      d.text(lines, MARGIN, this.y);
      this.y += lines.length * 4 + 2;
    } else {
      this.y += 2;
    }
  }

  paragraph(text: string, size = 9.5) {
    const d = this.doc;
    d.setFont("helvetica", "normal");
    d.setFontSize(size);
    this.setText(C.slate700);
    const lines = d.splitTextToSize(text, CONTENT_W);
    for (const row of lines) {
      this.ensureSpace(5);
      d.text(row, MARGIN, this.y);
      this.y += 4.8;
    }
    this.y += 2;
  }

  drawCover() {
    const d = this.doc;
    const snap = this.session.context_snapshot;
    const types = this.session.interview_types?.join(", ") || "mixed";
    const fb = this.fb;

    this.setFill(C.slate900);
    d.rect(0, 0, PAGE_W, 56, "F");
    this.setFill(C.brandDark);
    d.rect(0, 52, PAGE_W, 8, "F");

    this.drawApplyXaiWordmark(MARGIN, 7, 12, 15);

    d.setFont("helvetica", "bold");
    d.setFontSize(9);
    this.setText([191, 219, 254]);
    d.text("MOCK INTERVIEW REPORT", MARGIN, 26);

    d.setFontSize(20);
    this.setText(C.white);
    const title = snap.job_title || "Practice session";
    const titleLines = d.splitTextToSize(title, CONTENT_W - 44);
    d.text(titleLines, MARGIN, 36);

    d.setFont("helvetica", "normal");
    d.setFontSize(10);
    this.setText([203, 213, 225]);
    d.text(snap.company || "Company", MARGIN, 46);
    d.text(`${formatDateTime(this.session.updated_at)}  ·  ${types}`, MARGIN, 51);

    const overall = fb.overall_score;
    if (overall != null) {
      const cx = PAGE_W - MARGIN - 18;
      const cy = 28;
      this.setFill(C.brand);
      d.circle(cx, cy, 16, "F");
      d.setFont("helvetica", "bold");
      d.setFontSize(16);
      this.setText(C.white);
      d.text(String(overall), cx, cy + 2, { align: "center" });
      d.setFontSize(7);
      d.text("OVERALL", cx, cy + 8, { align: "center" });
    }

    this.y = 62;

    if (fb.knowledge_summary) {
      this.ensureSpace(28);
      this.setFill(C.slate50);
      this.setDraw(C.slate200);
      d.setLineWidth(0.2);
      const boxH = Math.min(36, 8 + d.splitTextToSize(fb.knowledge_summary, CONTENT_W - 8).length * 4.2);
      d.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, "FD");
      d.setFont("helvetica", "bold");
      d.setFontSize(9);
      this.setText(C.brandDark);
      d.text("Executive summary", MARGIN + 4, this.y + 6);
      d.setFont("helvetica", "normal");
      d.setFontSize(9);
      this.setText(C.slate700);
      const sumLines = d.splitTextToSize(fb.knowledge_summary, CONTENT_W - 8);
      d.text(sumLines, MARGIN + 4, this.y + 12);
      this.y += boxH + 6;
    }
  }

  drawAnalysisMeta() {
    const meta = this.fb.analysis_meta;
    const stats = buildMockInterviewReportStats(this.session, this.fb);
    if (!meta && stats.framesAnalyzed == null) return;
    this.ensureSpace(16);
    this.setFill(C.slate50);
    this.setDraw(C.slate200);
    this.doc.setLineWidth(0.2);
    this.doc.roundedRect(MARGIN, this.y, CONTENT_W, 14, 2, 2, "FD");
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(8);
    this.setText(C.slate700);
    const line1 = `Analysis: answer rubric (100) + on-camera behavior (55)${
      stats.framesAnalyzed ? ` · ${stats.framesAnalyzed} snapshot(s)` : ""
    } · authenticity · coaching`;
    this.doc.text(line1, MARGIN + 3, this.y + 5);
    const line2 = `Generated ${formatDateTime(stats.generatedAt ?? this.session.updated_at)}${
      meta?.behavior_concerns ? ` · ${meta.behavior_concerns} behavior concern(s)` : ""
    }`;
    this.doc.text(line2, MARGIN + 3, this.y + 10);
    this.y += 18;
  }

  drawKpiCards() {
    const fb = this.fb;
    const stats = buildMockInterviewReportStats(this.session, fb);

    const cards: { label: string; value: string; sub: string }[] = [
      { label: "Overall", value: fb.overall_score != null ? String(fb.overall_score) : "—", sub: "Interview performance" },
      { label: "Answer rubric", value: fb.rubric_overall != null ? String(fb.rubric_overall) : "—", sub: `${stats.rubricScored}/100 params` },
      { label: "On-camera behavior", value: stats.behaviorOverall != null ? String(stats.behaviorOverall) : "—", sub: `${stats.behaviorConcerns} concern(s) · 55 params` },
      { label: "Presentation", value: stats.presentationScore != null ? String(stats.presentationScore) : "—", sub: "Expression & gaze" },
      { label: "Answers", value: String(stats.candidateAnswers), sub: `${stats.turns} turns` },
      { label: "Conduct flags", value: String(stats.conductIssueCount), sub: stats.conductIssueCount ? "See behavior section" : "None flagged" },
    ];

    const gap = 3;
    const cols = 3;
    const cardW = (CONTENT_W - gap * (cols - 1)) / cols;
    const cardH = 22;
    this.ensureSpace(cardH * 2 + gap + 8);
    cards.forEach((card, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = MARGIN + col * (cardW + gap);
      const y = this.y + row * (cardH + gap);
      this.setFill(C.white);
      this.setDraw(C.slate200);
      this.doc.setLineWidth(0.25);
      this.doc.roundedRect(x, y, cardW, cardH, 2, 2, "FD");
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(7);
      this.setText(C.slate500);
      this.doc.text(card.label.toUpperCase(), x + 3, y + 5);
      this.doc.setFont("helvetica", "bold");
      this.doc.setFontSize(15);
      this.setText(C.slate900);
      this.doc.text(card.value, x + 3, y + 12);
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(7);
      this.setText(C.slate500);
      const subLines = this.doc.splitTextToSize(card.sub, cardW - 6);
      this.doc.text(subLines.slice(0, 2), x + 3, y + 16);
    });
    this.y += cardH * 2 + gap + 8;
  }

  async drawConcernsSummary() {
    const behavioral = this.fb.presentation?.behavioral_parameters ?? [];
    const concerns = behavioral.filter((r) => r.detected || r.status === "concern");
    const conduct = this.fb.presentation?.professional_conduct?.issues ?? [];
    if (!concerns.length && !conduct.length) return;

    this.sectionTitle("Flags & concerns summary", "Prohibited activity and behavioral concerns from camera analysis.");
    const rows: (string | number)[][] = [];
    for (const code of conduct) {
      rows.push(["Conduct", CONDUCT_LABELS[code] ?? code, this.fb.presentation?.professional_conduct?.notes || "—"]);
    }
    for (const r of concerns.slice(0, 20)) {
      rows.push([r.category_label, r.label, r.notes || "—"]);
    }
    await this.table(["Category", "Parameter", "Notes"], rows, {
      columnStyles: { 0: { cellWidth: 42 }, 1: { cellWidth: 48 }, 2: { cellWidth: CONTENT_W - 90 } },
    });
  }

  drawCategoryBarChart() {
    const cats = this.fb.rubric_categories ?? [];
    if (!cats.length) return;

    this.sectionTitle("Category performance", "Average scores across the 10 analysis categories.");
    this.ensureSpace(cats.length * 9 + 4);

    for (const cat of cats) {
      const avg = cat.average_score;
      const label = cat.category_label.length > 42 ? `${cat.category_label.slice(0, 40)}…` : cat.category_label;
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(8.5);
      this.setText(C.slate700);
      this.doc.text(label, MARGIN, this.y + 3);
      const scoreText = avg != null ? `${avg}` : "N/A";
      this.doc.setFont("helvetica", "bold");
      this.doc.text(scoreText, PAGE_W - MARGIN, this.y + 3, { align: "right" });
      this.drawScoreBar(MARGIN, this.y + 5, CONTENT_W, 3.5, avg);
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(7);
      this.setText(C.slate500);
      this.doc.text(`${cat.parameters_scored}/${cat.parameters_total} parameters scored`, MARGIN, this.y + 11);
      this.y += 13;
    }
    this.y += 4;
  }

  async table(
    head: string[],
    body: (string | number)[][],
    opts?: {
      columnStyles?: Record<number, { cellWidth?: number; halign?: "left" | "center" | "right" }>;
      bodyStyles?: Record<number, { fillColor?: RGB; textColor?: RGB }>;
      scoreBarColumn?: number;
      scores?: (number | null | undefined)[];
    },
  ) {
    const autoTable = (await import("jspdf-autotable")).default;
    const d = this.doc;
    this.ensureSpace(20);

    autoTable(d, {
      startY: this.y,
      margin: { left: MARGIN, right: MARGIN },
      head: [head],
      body,
      theme: "grid",
      styles: {
        font: "helvetica",
        fontSize: 8.5,
        cellPadding: 2.5,
        lineColor: [...C.slate200],
        lineWidth: 0.15,
        textColor: [...C.slate700],
        overflow: "linebreak",
      },
      headStyles: {
        fillColor: [...C.brand],
        textColor: [...C.white],
        fontStyle: "bold",
        fontSize: 8.5,
      },
      alternateRowStyles: { fillColor: [...C.slate50] },
      columnStyles: opts?.columnStyles,
      didDrawCell: (data) => {
        if (opts?.scoreBarColumn == null || data.section !== "body" || data.column.index !== opts.scoreBarColumn) return;
        const rowIdx = data.row.index;
        const score = opts.scores?.[rowIdx];
        if (score == null) return;
        const pad = 2;
        const barX = data.cell.x + pad;
        const barY = data.cell.y + data.cell.height - 5;
        const barW = data.cell.width - pad * 2;
        this.drawScoreBar(barX, barY, barW, 2.5, score);
      },
    });

    const finalY = (d as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY;
    this.y = (finalY ?? this.y) + 8;
  }

  addFooters() {
    const d = this.doc;
    const total = d.getNumberOfPages();
    const snap = this.session.context_snapshot;
    const meta = `${snap.job_title || "Session"} · ${snap.company || ""}`.trim();

    for (let p = 1; p <= total; p++) {
      d.setPage(p);
      d.setDrawColor(C.slate200[0], C.slate200[1], C.slate200[2]);
      d.setLineWidth(0.2);
      d.line(MARGIN, FOOTER_Y - 4, PAGE_W - MARGIN, FOOTER_Y - 4);
      d.setFont("helvetica", "normal");
      d.setFontSize(7);
      this.setText(C.slate500);
      const footerText = `${APP_NAME}  ·  ${meta}`;
      if (this.mascotDataUrl) {
        d.addImage(this.mascotDataUrl, "PNG", MARGIN, FOOTER_Y - 5.5, 4.5, 4.5);
        d.text(footerText, MARGIN + 6, FOOTER_Y);
      } else {
        d.text(footerText, MARGIN, FOOTER_Y);
      }
      d.text(`Page ${p} of ${total}`, PAGE_W - MARGIN, FOOTER_Y, { align: "right" });
    }
  }

  async build() {
    this.drawCover();
    this.drawAnalysisMeta();
    this.drawKpiCards();
    await this.drawConcernsSummary();

    const fb = this.fb;
    const dims = fb.dimensions ?? [];
    if (dims.length > 0) {
      this.sectionTitle("Core dimensions", "Key competency scores from your session.");
      await this.table(
        ["Dimension", "Score", "Progress", "Notes"],
        dims.map((d) => [d.label, `${d.score}/100`, "", d.notes || "—"]),
        {
          columnStyles: {
            0: { cellWidth: 42 },
            1: { cellWidth: 18, halign: "center" },
            2: { cellWidth: 38 },
            3: { cellWidth: CONTENT_W - 42 - 18 - 38 },
          },
          scoreBarColumn: 2,
          scores: dims.map((d) => d.score),
        },
      );
    }

    await this.drawCategoryBarChart();

    if (fb.presentation?.available) {
      const p = fb.presentation;
      this.sectionTitle("On-camera presence", "Expression, eye contact, grooming, and professional conduct from snapshots.");
      const conductIssues = p.professional_conduct?.issues ?? [];
      if (conductIssues.length > 0) {
        await this.table(
          ["Conduct issue", "Details"],
          conductIssues.map((code) => [
            CONDUCT_LABELS[code] ?? code.replace(/_/g, " "),
            p.professional_conduct?.notes || "Flagged in camera snapshots.",
          ]),
          { columnStyles: { 0: { cellWidth: 52 } } },
        );
        if (p.professional_conduct?.score != null) {
          this.drawScoreBar(MARGIN, this.y, CONTENT_W, 4, p.professional_conduct.score);
          this.doc.setFontSize(8);
          this.setText(C.slate500);
          this.doc.text(`Professional conduct score: ${p.professional_conduct.score}/100`, MARGIN, this.y + 8);
          this.y += 12;
        }
      }
      const rows: (string | number)[][] = [];
      const scores: (number | null | undefined)[] = [];
      if (p.overall_score != null) {
        rows.push(["Overall presentability", `${p.overall_score}/100`, "", p.presentability_summary || "—"]);
        scores.push(p.overall_score);
      }
      if (p.facial_expression) {
        rows.push(["Facial expression", `${p.facial_expression.score}/100`, "", p.facial_expression.notes]);
        scores.push(p.facial_expression.score);
      }
      if (p.eye_contact) {
        rows.push(["Eye contact", `${p.eye_contact.score}/100`, "", p.eye_contact.notes]);
        scores.push(p.eye_contact.score);
      }
      if (p.grooming) {
        rows.push(["Grooming", `${p.grooming.score}/100`, "", p.grooming.notes]);
        scores.push(p.grooming.score);
      }
      if (rows.length) {
        await this.table(["Metric", "Score", "Progress", "Coach notes"], rows, {
          columnStyles: { 0: { cellWidth: 42 }, 1: { cellWidth: 18, halign: "center" }, 2: { cellWidth: 38 } },
          scoreBarColumn: 2,
          scores,
        });
      }
    } else if (fb.presentation?.presentability_summary) {
      this.sectionTitle("On-camera presence");
      this.paragraph(fb.presentation.presentability_summary);
    }

    const behavioral = fb.presentation?.behavioral_parameters ?? [];
    if (behavioral.length > 0) {
      this.sectionTitle(
        "On-camera behavioral analysis",
        "55 parameters: gaze, expression, posture, gestures, video quality, prohibited acts, distractions, integrity.",
      );
      if (fb.presentation?.behavior_overall != null) {
        this.paragraph(`Behavioral average score: ${fb.presentation.behavior_overall}/100`);
      }
      const catOrder: string[] = [];
      for (const row of behavioral) {
        if (!catOrder.includes(row.category_label)) catOrder.push(row.category_label);
      }
      for (const catLabel of catOrder) {
        const rows = behavioral.filter((r) => r.category_label === catLabel);
        this.ensureSpace(12);
        this.doc.setFont("helvetica", "bold");
        this.doc.setFontSize(10);
        this.setText(C.brandDark);
        this.doc.text(catLabel, MARGIN, this.y);
        this.y += 5;
        await this.table(
          ["#", "Parameter", "Status", "Score", "Notes"],
          rows.map((r) => [
            r.id,
            r.label,
            r.detected || r.status === "concern" ? "Concern" : r.status ?? "—",
            r.score != null ? `${r.score}` : "—",
            r.notes || "—",
          ]),
          {
            columnStyles: {
              0: { cellWidth: 8, halign: "center" },
              1: { cellWidth: 48 },
              2: { cellWidth: 22, halign: "center" },
              3: { cellWidth: 14, halign: "center" },
              4: { cellWidth: CONTENT_W - 8 - 48 - 22 - 14 },
            },
          },
        );
      }
    }

    if (fb.answer_authenticity) {
      const a = fb.answer_authenticity;
      this.sectionTitle("Answer authenticity", "How naturally your answers sounded versus scripted text.");
      await this.table(
        ["Assessment", "Confidence", "Notes & signals"],
        [
          [
            AUTHENTICITY_LABELS[a.overall] ?? a.overall,
            a.confidence != null ? `${a.confidence}%` : "—",
            [a.notes, ...(a.signals ?? []).map((s) => `• ${s}`)].filter(Boolean).join("\n") || "—",
          ],
        ],
        { columnStyles: { 0: { cellWidth: 45 }, 1: { cellWidth: 22, halign: "center" } } },
      );
    }

    const qBreak = fb.question_breakdown ?? [];
    if (qBreak.length > 0) {
      this.sectionTitle("Question-by-question review", "Interviewer prompts and answer quality.");
      await this.table(
        ["#", "Question", "Quality", "Feedback"],
        qBreak.map((row, i) => [i + 1, row.question, row.answer_quality, row.notes || "—"]),
        {
          columnStyles: {
            0: { cellWidth: 8, halign: "center" },
            1: { cellWidth: 72 },
            2: { cellWidth: 22, halign: "center" },
            3: { cellWidth: CONTENT_W - 8 - 72 - 22 },
          },
        },
      );
    }

    if ((fb.strengths ?? []).length > 0 || (fb.improvements ?? []).length > 0) {
      this.sectionTitle("Coaching highlights");
      const maxLen = Math.max(fb.strengths?.length ?? 0, fb.improvements?.length ?? 0);
      const body: (string | number)[][] = [];
      for (let i = 0; i < maxLen; i++) {
        body.push([fb.strengths?.[i] ? `+ ${fb.strengths[i]}` : "", fb.improvements?.[i] ? `→ ${fb.improvements[i]}` : ""]);
      }
      await this.table(["Strengths", "Improve next time"], body, {
        columnStyles: { 0: { cellWidth: CONTENT_W / 2 }, 1: { cellWidth: CONTENT_W / 2 } },
      });
    }

    if ((fb.sample_answers ?? []).length > 0) {
      this.sectionTitle("Stronger answer examples");
      await this.table(
        ["Question", "Suggested approach"],
        fb.sample_answers!.map((item) => [item.question, item.suggestion]),
        { columnStyles: { 0: { cellWidth: 65 } } },
      );
    }

    const rubric = [...(fb.rubric_scores ?? [])].sort((a, b) => a.id - b.id);
    if (rubric.length > 0) {
      this.sectionTitle("Detailed rubric (100 parameters)", "Full scoring grid grouped by category.");
      const byCat = new Map<string, typeof rubric>();
      for (const row of rubric) {
        const key = row.category_label || row.category_id;
        const list = byCat.get(key) ?? [];
        list.push(row);
        byCat.set(key, list);
      }
      for (const [catLabel, rows] of byCat) {
        this.ensureSpace(14);
        this.doc.setFont("helvetica", "bold");
        this.doc.setFontSize(10);
        this.setText(C.brandDark);
        this.doc.text(catLabel, MARGIN, this.y);
        this.y += 5;
        await this.table(
          ["#", "Parameter", "Score", "Notes"],
          rows.map((p) => [p.id, p.label, p.score != null ? `${p.score}/100` : "N/A", p.notes || "—"]),
          {
            columnStyles: {
              0: { cellWidth: 10, halign: "center" },
              1: { cellWidth: 62 },
              2: { cellWidth: 18, halign: "center" },
              3: { cellWidth: CONTENT_W - 10 - 62 - 18 },
            },
          },
        );
      }
    }

    if (this.session.messages.length > 0) {
      this.sectionTitle("Full transcript", "Complete interviewer and candidate dialogue.");
      await this.table(
        ["Speaker", "Message"],
        this.session.messages.map((m) => [
          m.role === "interviewer" ? "Interviewer" : "You",
          m.content,
        ]),
        {
          columnStyles: {
            0: { cellWidth: 26, halign: "center" },
            1: { cellWidth: CONTENT_W - 26 },
          },
        },
      );
    }

    if (fb.error) {
      this.sectionTitle("Analysis note");
      this.paragraph(fb.error);
    }

    this.addFooters();
  }
}

export async function exportMockInterviewReportPdf(
  session: MockInterviewSessionDetail,
  feedback: MockInterviewFeedback,
): Promise<void> {
  const mascotDataUrl = await loadApplyXaiMascotDataUrl();
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const report = new ReportPdf(doc, session, feedback, mascotDataUrl);
  report.drawPageWatermark();
  await report.build();
  doc.save(mockInterviewReportPdfFilename(session));
}
