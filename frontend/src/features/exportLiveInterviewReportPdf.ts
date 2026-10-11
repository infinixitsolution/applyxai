import type { jsPDF } from "jspdf";
import { APP_NAME } from "../lib/config";
import { formatDateTime } from "../lib/format";
import type { LiveInterviewSession } from "../types";
import { loadApplyXaiMascotDataUrl, PDF_WATERMARK_TEXT } from "./pdfApplyXaiBranding";
import {
  PDF_FONTS,
  normalizePdfText,
  rasterizePdfText,
  textDrawsWithoutShaping,
  textNeedsRaster,
  wrapPdfLines,
  type PdfFontName,
  type PdfTextImage,
} from "./pdfUnicodeText";

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

function durationLabel(start?: string | null, end?: string | null) {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const minutes = Math.round(ms / 60000);
  return minutes < 1 ? "<1 min" : `${minutes} min`;
}

function scoreBarColor(score: number): RGB {
  if (score >= 70) return C.emerald;
  if (score >= 45) return C.brand;
  if (score >= 20) return C.amber;
  return C.red;
}

function bytesToBinary(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return binary;
}

class LiveReportPdf {
  doc: jsPDF;
  y = MARGIN;
  session: LiveInterviewSession;
  mascotDataUrl: string | null;
  fonts = new Set<string>();

  constructor(doc: jsPDF, session: LiveInterviewSession, mascotDataUrl: string | null) {
    this.doc = doc;
    this.session = session;
    this.mascotDataUrl = mascotDataUrl;
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
    d.text("Confidential · Live interview report", PAGE_W / 2, PAGE_H / 2 + 14, { align: "center", angle: 38 });
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

  async loadFonts() {
    for (const font of PDF_FONTS) {
      try {
        const response = await fetch(`/fonts/${font.file}`);
        if (!response.ok) continue;
        const buffer = await response.arrayBuffer();
        this.doc.addFileToVFS(font.file, bytesToBinary(buffer));
        this.doc.addFont(font.file, font.name, "normal");
        this.fonts.add(font.name);
      } catch {
        /* This script stays as a painted image. */
      }
    }
  }

  private measureRun(text: string, font: PdfFontName): number {
    this.doc.setFont(font, "normal");
    this.doc.setFontSize(8.5);
    return this.doc.getTextWidth(text);
  }

  private drawSelectableLayer(image: PdfTextImage, left: number, top: number) {
    const d = this.doc;
    d.setFontSize(8.5);
    image.lines.forEach((text, index) => {
      const y = top + index * image.lineHeightMm + image.lineHeightMm * 0.75;
      let x = left;
      for (const line of wrapPdfLines(text, Number.POSITIVE_INFINITY, (value, font) => this.measureRun(value, font), this.fonts)) {
        for (const part of line) {
          d.setFont(part.font, "normal");
          d.setFontSize(8.5);
          d.text(part.text, x, y, { renderingMode: "invisible" });
          x += d.getTextWidth(part.text);
        }
      }
    });
    d.setFont("helvetica", "normal");
  }

  async table(
    head: string[],
    body: (string | number)[][],
    columnStyles?: Record<number, { cellWidth?: number; halign?: "left" | "center" | "right" }>,
  ) {
    const autoTable = (await import("jspdf-autotable")).default;
    const d = this.doc;
    this.ensureSpace(20);
    const images = new Map<string, PdfTextImage>();
    const unicode = new Map<string, ReturnType<typeof wrapPdfLines>>();
    const fallbackWidth = CONTENT_W / Math.max(head.length, 1);
    const safeBody = body.map((row, rowIndex) =>
      row.map((cell, columnIndex) => {
        const text = normalizePdfText(String(cell ?? ""));
        const columnWidth = columnStyles?.[columnIndex]?.cellWidth ?? fallbackWidth;
        if (textNeedsRaster(text) && textDrawsWithoutShaping(text, this.fonts)) {
          unicode.set(`${rowIndex}:${columnIndex}`, wrapPdfLines(text, Math.max(20, columnWidth - 5), (value, font) => this.measureRun(value, font)));
        } else if (textNeedsRaster(text)) {
          images.set(`${rowIndex}:${columnIndex}`, rasterizePdfText(text, Math.max(20, columnWidth - 5), 8.5));
        }
        return text;
      }),
    );
    autoTable(d, {
      startY: this.y,
      margin: { left: MARGIN, right: MARGIN },
      head: [head.map((label) => normalizePdfText(label))],
      body: safeBody,
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
      columnStyles,
      didParseCell: (data) => {
        if (data.section !== "body") return;
        const key = `${data.row.index}:${data.column.index}`;
        const lines = unicode.get(key);
        const image = images.get(key);
        if (!lines && !image) return;
        data.cell.text = [];
        data.cell.styles.minCellHeight = lines ? lines.length * 4 + 5 : (image?.heightMm ?? 0) + 5;
      },
      didDrawCell: (data) => {
        if (data.section !== "body") return;
        const key = `${data.row.index}:${data.column.index}`;
        const lines = unicode.get(key);
        if (lines) {
          d.setFontSize(8.5);
          this.setText(C.slate700);
          let y = data.cell.y + 5.2;
          for (const line of lines) {
            let x = data.cell.x + 2.5;
            for (const run of line) {
              d.setFont(run.font, "normal");
              d.text(run.text, x, y);
              x += d.getTextWidth(run.text);
            }
            y += 4;
          }
          d.setFont("helvetica", "normal");
          return;
        }
        const image = images.get(key);
        if (!image) return;
        const left = data.cell.x + 2.5;
        const top = data.cell.y + 2.5;
        d.addImage(image.dataUrl, "PNG", left, top, image.widthMm, image.heightMm, undefined, "FAST");
        this.drawSelectableLayer(image, left, top);
      },
    });
    const finalY = (d as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY;
    this.y = (finalY ?? this.y) + 8;
  }

  drawCover() {
    const d = this.doc;
    const fb = this.session.feedback;
    const title = this.session.job_title || "Live interview";
    this.setFill(C.slate900);
    d.rect(0, 0, PAGE_W, 56, "F");
    this.setFill(C.brandDark);
    d.rect(0, 52, PAGE_W, 8, "F");
    this.drawApplyXaiWordmark(MARGIN, 7, 12, 15);
    d.setFont("helvetica", "bold");
    d.setFontSize(9);
    this.setText([191, 219, 254]);
    d.text("LIVE INTERVIEW REPORT", MARGIN, 26);
    d.setFontSize(18);
    this.setText(C.white);
    const titleLines = d.splitTextToSize(normalizePdfText(title), CONTENT_W - 44);
    d.text(titleLines, MARGIN, 36);
    d.setFont("helvetica", "normal");
    d.setFontSize(10);
    this.setText([203, 213, 225]);
    d.text(normalizePdfText(this.session.company || "No job selected"), MARGIN, 46);
    d.text(
      `${formatDateTime(this.session.ended_at || this.session.started_at)}  ·  ${durationLabel(this.session.started_at, this.session.ended_at)}`,
      MARGIN,
      51,
    );
    const overall = fb?.overall_score;
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
    this.y = 66;
    const summary = normalizePdfText(fb?.knowledge_summary || fb?.summary || "");
    if (summary && textNeedsRaster(summary)) {
      const painted = rasterizePdfText(summary, CONTENT_W - 8, 9);
      const boxH = painted.heightMm + 12;
      this.ensureSpace(boxH + 6);
      this.setFill(C.slate50);
      this.setDraw(C.slate200);
      d.setLineWidth(0.2);
      d.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, "FD");
      d.setFont("helvetica", "bold");
      d.setFontSize(9);
      this.setText(C.brandDark);
      d.text("Executive summary", MARGIN + 4, this.y + 6);
      d.addImage(painted.dataUrl, "PNG", MARGIN + 4, this.y + 8, painted.widthMm, painted.heightMm, undefined, "FAST");
      this.drawSelectableLayer(painted, MARGIN + 4, this.y + 8);
      this.y += boxH + 6;
    } else if (summary) {
      const lines = d.splitTextToSize(summary, CONTENT_W - 8);
      const boxH = 8 + lines.length * 4.2;
      this.ensureSpace(boxH + 6);
      this.setFill(C.slate50);
      this.setDraw(C.slate200);
      d.setLineWidth(0.2);
      d.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, "FD");
      d.setFont("helvetica", "bold");
      d.setFontSize(9);
      this.setText(C.brandDark);
      d.text("Executive summary", MARGIN + 4, this.y + 6);
      d.setFont("helvetica", "normal");
      d.setFontSize(9);
      this.setText(C.slate700);
      d.text(lines, MARGIN + 4, this.y + 12);
      this.y += boxH + 6;
    }
  }

  drawKpis() {
    const fb = this.session.feedback;
    const transcript = this.session.transcript ?? [];
    const answers = transcript.filter((turn) => turn.role === "candidate").length;
    const questions = transcript.filter((turn) => turn.role === "interviewer").length;
    const coaching = transcript.filter((turn) => turn.role === "suggestion").length;
    const scored = (fb?.rubric_scores ?? []).filter((row) => row.score != null).length;
    const cards = [
      { label: "Overall", value: fb?.overall_score != null ? String(fb.overall_score) : "—", sub: "Spoken answers" },
      { label: "Answer rubric", value: fb?.rubric_overall != null ? String(fb.rubric_overall) : "—", sub: `${scored}/100 params` },
      { label: "Your answers", value: String(answers), sub: `${questions} interviewer lines` },
      { label: "Coaching lines", value: String(coaching), sub: "Not scored" },
      { label: "Duration", value: durationLabel(this.session.started_at, this.session.ended_at), sub: "Desktop session" },
      { label: "Questions", value: String(fb?.question_breakdown?.length ?? 0), sub: "Reviewed prompts" },
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
      this.doc.text(this.doc.splitTextToSize(card.sub, cardW - 6).slice(0, 2), x + 3, y + 16);
    });
    this.y += cardH * 2 + gap + 8;
  }

  drawCategories() {
    const cats = this.session.feedback?.rubric_categories ?? [];
    if (!cats.length) return;
    this.sectionTitle("Category performance", "Average scores across the 10 analysis categories.");
    for (const cat of cats) {
      this.ensureSpace(14);
      const fullLabel = normalizePdfText(cat.category_label);
      const label = fullLabel.length > 42 ? `${fullLabel.slice(0, 40)}...` : fullLabel;
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(8.5);
      this.setText(C.slate700);
      this.doc.text(label, MARGIN, this.y + 3);
      this.doc.setFont("helvetica", "bold");
      this.doc.text(cat.average_score != null ? String(cat.average_score) : "N/A", PAGE_W - MARGIN, this.y + 3, { align: "right" });
      this.drawScoreBar(MARGIN, this.y + 5, CONTENT_W, 3.5, cat.average_score);
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(7);
      this.setText(C.slate500);
      this.doc.text(`${cat.parameters_scored}/${cat.parameters_total} parameters scored`, MARGIN, this.y + 11);
      this.y += 13;
    }
    this.y += 4;
  }

  async build() {
    const fb = this.session.feedback;
    this.drawCover();
    this.drawKpis();
    this.drawCategories();
    if ((fb?.dimensions ?? []).length) {
      this.sectionTitle("Core dimensions");
      await this.table(
        ["Dimension", "Score", "Notes"],
        fb!.dimensions!.map((row) => [row.label || row.key || "Dimension", row.score != null ? `${row.score}/100` : "—", row.notes || "—"]),
        { 0: { cellWidth: 42 }, 1: { cellWidth: 22, halign: "center" }, 2: { cellWidth: CONTENT_W - 64 } },
      );
    }
    if ((fb?.question_breakdown ?? []).length) {
      this.sectionTitle("Question-by-question review", "Interviewer prompts and how the spoken answer landed.");
      await this.table(
        ["#", "Question", "Quality", "Feedback"],
        fb!.question_breakdown!.map((row, i) => [i + 1, row.question || "—", row.answer_quality || "—", row.notes || "—"]),
        { 0: { cellWidth: 8, halign: "center" }, 1: { cellWidth: 72 }, 2: { cellWidth: 22, halign: "center" }, 3: { cellWidth: CONTENT_W - 102 } },
      );
    }
    const strengths = fb?.strengths ?? [];
    const tips = fb?.suggestions ?? [];
    if (strengths.length || tips.length) {
      this.sectionTitle("Coaching highlights");
      const maxLen = Math.max(strengths.length, tips.length);
      const body: string[][] = [];
      for (let i = 0; i < maxLen; i++) {
        body.push([strengths[i] ? `+ ${strengths[i]}` : "", tips[i] ? `→ ${tips[i]}` : ""]);
      }
      await this.table(["Strengths", "Improve next time"], body, { 0: { cellWidth: CONTENT_W / 2 }, 1: { cellWidth: CONTENT_W / 2 } });
    }
    if ((fb?.sample_answers ?? []).length) {
      this.sectionTitle("Stronger answer examples");
      await this.table(
        ["Question", "Suggested approach"],
        fb!.sample_answers!.map((item) => [item.question || "—", item.suggestion || "—"]),
        { 0: { cellWidth: 65 } },
      );
    }
    const rubric = [...(fb?.rubric_scores ?? [])].sort((a, b) => a.id - b.id);
    if (rubric.length) {
      this.sectionTitle("Detailed rubric (100 parameters)", "Same scoring grid as a mock interview. N/A means the conversation did not cover that signal.");
      const byCat = new Map<string, typeof rubric>();
      for (const row of rubric) {
        const key = row.category_label || row.category_id;
        const list = byCat.get(key) ?? [];
        list.push(row);
        byCat.set(key, list);
      }
      for (const [label, rows] of byCat) {
        this.ensureSpace(14);
        this.doc.setFont("helvetica", "bold");
        this.doc.setFontSize(10);
        this.setText(C.brandDark);
        this.doc.text(label, MARGIN, this.y);
        this.y += 5;
        await this.table(
          ["#", "Parameter", "Score", "Notes"],
          rows.map((row) => [row.id, row.label, row.score != null ? `${row.score}/100` : "N/A", row.notes || "—"]),
          { 0: { cellWidth: 10, halign: "center" }, 1: { cellWidth: 62 }, 2: { cellWidth: 18, halign: "center" }, 3: { cellWidth: CONTENT_W - 90 } },
        );
      }
    }
    const transcript = this.session.transcript ?? [];
    if (transcript.length) {
      this.sectionTitle("Conversation", "Interviewer, the suggested answer shown on screen, and what you said.");
      const who = { interviewer: "Interviewer", suggestion: "Suggested answer", candidate: "You" };
      await this.table(
        ["Speaker", "Message"],
        transcript.map((turn) => [who[turn.role] || turn.role, turn.text]),
        { 0: { cellWidth: 32, halign: "center" }, 1: { cellWidth: CONTENT_W - 32 } },
      );
    }
    this.addFooters();
  }

  addFooters() {
    const d = this.doc;
    const total = d.getNumberOfPages();
    const meta = `${this.session.job_title || "Live interview"} · ${this.session.company || ""}`.trim();
    for (let page = 1; page <= total; page++) {
      d.setPage(page);
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
      d.text(`Page ${page} of ${total}`, PAGE_W - MARGIN, FOOTER_Y, { align: "right" });
    }
  }
}

export async function exportLiveInterviewReportPdf(session: LiveInterviewSession): Promise<void> {
  const mascotDataUrl = await loadApplyXaiMascotDataUrl();
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const report = new LiveReportPdf(doc, session, mascotDataUrl);
  await report.loadFonts();
  report.drawPageWatermark();
  await report.build();
  const date = (session.ended_at || session.started_at || "").slice(0, 10) || "report";
  const company = sanitizeFilename(session.company || session.job_title || "live-interview");
  doc.save(`live-interview-${company}-${date}.pdf`);
}
