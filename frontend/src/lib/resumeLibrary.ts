import type { Resume } from "../types";

export type ResumeKind = "upload" | "ai" | "automation" | "style";

export function resumeKind(r: Resume): ResumeKind {
  const by = String(r.ai_metadata?.generated_by ?? "").toLowerCase();
  if (by === "ai") return "ai";
  if (by === "automation") return "automation";
  if (by === "style") return "style";
  return "upload";
}

export function isBuiltResume(r: Resume): boolean {
  return resumeKind(r) !== "upload";
}

export function builtResumeLabel(kind: ResumeKind): string {
  if (kind === "ai") return "Tailored";
  if (kind === "automation") return "Auto apply";
  if (kind === "style") return "Styled";
  return "Upload";
}

export function builtResumeJobLine(r: Resume): string | null {
  const m = r.ai_metadata ?? {};
  const title = typeof m.job_title === "string" ? m.job_title.trim() : "";
  const company = typeof m.company === "string" ? m.company.trim() : "";
  const line = [title, company].filter(Boolean).join(" · ");
  if (line) return line;
  const jobId = typeof m.job_id === "string" ? m.job_id.trim() : "";
  return jobId ? `LinkedIn job ${jobId}` : null;
}

export function splitResumeLibrary(resumes: Resume[]): { built: Resume[]; uploads: Resume[] } {
  const built: Resume[] = [];
  const uploads: Resume[] = [];
  for (const r of resumes) {
    if (isBuiltResume(r)) built.push(r);
    else uploads.push(r);
  }
  const byNewest = (a: Resume, b: Resume) => (b.created_at ?? "").localeCompare(a.created_at ?? "");
  built.sort(byNewest);
  uploads.sort(byNewest);
  return { built, uploads };
}
