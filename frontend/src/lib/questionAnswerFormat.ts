import type { PendingFormQuestion } from "../types";

export type AnswerFormat = "choice" | "number" | "text";

const NUMERIC_LABEL =
  /how many|number of|# of|years?\s+of|years?\s+experience|months?\s+of|weeks?\s+of|notice\s+period|salary|compensation|\bctc\b|pay\s+rate|hourly|annual|gpa|percent|percentage|scale\s+of\s*1|team\s+size/i;

export function inferAnswerFormat(label: string, questionType: string): AnswerFormat {
  const qt = (questionType || "text").toLowerCase();
  if (qt === "select" || qt === "radio") return "choice";
  if (qt === "number" || qt === "tel") return "number";
  const text = (label || "").trim();
  if (NUMERIC_LABEL.test(text)) return "number";
  if (/\b\d+\s*\+?\s*years?\b/i.test(text)) return "number";
  return "text";
}

export function formatForQuestion(q: PendingFormQuestion): AnswerFormat {
  const opts = (q.options ?? []).filter((o) => o.trim().length > 0);
  if ((q.question_type === "select" || q.question_type === "radio") && opts.length > 0) {
    return "choice";
  }
  return inferAnswerFormat(q.label, q.question_type);
}

export function numericPresetsForLabel(label: string): string[] {
  const low = label.toLowerCase();
  if (low.includes("scale") && low.includes("1")) {
    return Array.from({ length: 10 }, (_, i) => String(i + 1));
  }
  if (low.includes("notice")) return ["0", "7", "15", "30", "45", "60", "90"];
  if (/year|experience|how many/i.test(low)) {
    return Array.from({ length: 21 }, (_, i) => String(i));
  }
  if (/salary|ctc|compensation|pay/i.test(low)) {
    return ["500000", "800000", "1000000", "1200000", "1500000", "2000000"];
  }
  if (low.includes("month")) return Array.from({ length: 25 }, (_, i) => String(i));
  if (low.includes("week")) return Array.from({ length: 53 }, (_, i) => String(i));
  return Array.from({ length: 11 }, (_, i) => String(i));
}

export function textPresetsForLabel(label: string): string[] {
  const low = label.toLowerCase();
  if (low.includes("authorized") || (low.includes("legally") && low.includes("work"))) {
    return ["Yes", "No"];
  }
  if (low.includes("sponsor") || low.includes("visa")) return ["Yes", "No", "Not applicable"];
  if (low.startsWith("are you") || low.startsWith("do you")) return ["Yes", "No"];
  return [];
}

export const CUSTOM_ANSWER = "__custom__";
